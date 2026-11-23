"""Authenticated API for Getangiru native multiactor simulation and reports."""
from __future__ import annotations

import json
import hashlib
import os
import re
import threading
from pathlib import Path
from flask import Blueprint, Response, jsonify, request

from ..auth import can_access_project, is_admin
from ..config import Config
from ..models.project import ProjectManager, ProjectStatus
from ..services.getangiru_graph_engine import default_store
from ..services.getangiru_native_simulation import default_native_sim_store
from ..utils.local_model import local_inference_requested, local_inference_ready
from ..utils.llm_client import LLMClient

native_sim_bp = Blueprint("native_simulation", __name__)
PROJECT_RE = re.compile(r"^proj_[0-9a-f]{12}$")
ID_RE = re.compile(r"^lsim_[0-9a-f]{24}$")


def _store():
    return default_native_sim_store(Config.UPLOAD_FOLDER)


def _get_owned_run(run_id):
    if not ID_RE.fullmatch(run_id):
        return None
    result = _store().get(run_id)
    if not result or not can_access_project(result["project_id"]):
        return None
    return result


def _project_readable(project_id):
    if not PROJECT_RE.fullmatch(project_id) or not can_access_project(project_id):
        return None
    return ProjectManager.get_project(project_id)


@native_sim_bp.get("/capabilities")
def capabilities():
    return jsonify({"success": True, "data": {
        "engine": "getangiru_native_v1",
        "graph_local_enabled": os.getenv("GETANGIRU_GRAPH_LOCAL_ENABLED","false").lower()=="true",
        "local_inference_enabled": local_inference_requested(),
        "local_model_ready": local_inference_ready() if local_inference_requested() else False,
        "simulation_modes": ["rules", "hybrid"],
        "external_research": "explicit_opt_in_only",
        "external_research_enabled": os.getenv("GETANGIRU_PUBLIC_RESEARCH_ENABLED","false").lower()=="true",
        "simulation_is_hypothetical": True,
        "independent_of_zep": True,
        "max_agents": 12, "max_phases": 4,
    }})


@native_sim_bp.post("/public-cve")
def public_cve_lookup():
    """Explicit, bounded public-data search. Never uploads project content."""
    if os.getenv("GETANGIRU_PUBLIC_RESEARCH_ENABLED","false").lower()!="true":
        return jsonify({"success":False,"error":"Consultas externas deshabilitadas por política"}),403
    data=request.get_json(silent=True) or {}
    if set(data.keys())!={"cves"}:
        return jsonify({"success":False,"error":"Solo se permiten identificadores CVE explícitos"}),422
    from ..services.getangiru_public_research import lookup_public_cves
    try:
        result=lookup_public_cves(data.get("cves"),Path(Config.UPLOAD_FOLDER)/"getangiru"/"public-kev-cache.json")
    except ValueError:
        return jsonify({"success":False,"error":"Ingresá entre 1 y 5 identificadores CVE válidos"}),422
    except (OSError,RuntimeError,TimeoutError):
        return jsonify({"success":False,"error":"Catálogo público no disponible; no se enviaron datos internos"}),503
    return jsonify({"success":True,"data":result})


@native_sim_bp.post("/start")
def start():
    data = request.get_json(silent=True) or {}
    project_id = data.get("project_id")
    if not isinstance(project_id,str) or not PROJECT_RE.fullmatch(project_id):
        return jsonify({"success":False,"error":"Proyecto inválido"}),400
    project=_project_readable(project_id)
    if not project:
        return jsonify({"success":False,"error":"Proyecto no disponible"}),404
    if os.getenv("GETANGIRU_GRAPH_LOCAL_ENABLED","false").lower()!="true":
        return jsonify({"success":False,"error":"Motor Getangiru local deshabilitado"}),503
    if project.status!=ProjectStatus.GRAPH_COMPLETED or not project.graph_id or not project.graph_id.startswith("gtg_"):
        return jsonify({"success":False,"error":"Primero construí el grafo local del proyecto"}),409
    if set(data.keys()) != {"project_id","mode"} and set(data.keys()) != {"project_id"}:
        return jsonify({"success":False,"error":"Campos de simulación desconocidos"}),422
    mode=data.get("mode","hybrid")
    if mode not in ("hybrid","rules"):
        return jsonify({"success":False,"error":"Modo de inferencia inválido"}),422
    if mode=="hybrid" and (not local_inference_requested() or not local_inference_ready()):
        return jsonify({"success":False,"error":"Qwen local no está disponible. Elegí reglas o revisá el motor."}),503
    # Security: no supplied graph_id; the current persisted project owns it.
    store=default_store(Config.UPLOAD_FOLDER)
    try:
        graph=store.read(project.graph_id,tenant="tenondera",project_id=project_id)
    except (KeyError,ValueError):
        return jsonify({"success":False,"error":"Grafo local no disponible"}),409
    if not 1<=graph["node_count"]<=12:
        return jsonify({"success":False,"error":"El piloto permite de 1 a 12 actores por simulación"}),422
    objective=(project.simulation_requirement or "Revisión de controles y respuesta hipotética")[:600]
    sim_store=_store()
    try:
        source_hash=hashlib.sha256(json.dumps({
            "graph_id":graph["graph_id"],"nodes":graph["nodes"],"edges":graph["edges"],
            "schema_relations":graph.get("schema_relations",[])
        },sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()
        run=sim_store.create(project_id=project_id,graph_id=project.graph_id,mode=mode,
                             source_hash=source_hash)
    except RuntimeError:
        return jsonify({"success":False,"error":"Hay una simulación en ejecución; consultá su progreso."}),409
    except ValueError:
        return jsonify({"success":False,"error":"Se alcanzó el límite de ejecuciones de este proyecto; archivá los resultados."}),429
    def worker():
        model=None
        try:
            model=LLMClient() if mode=="hybrid" else None
            if model is not None:
                # One short, local, non-retried Qwen call per full simulation.
                model.client=model.client.with_options(timeout=55.0,max_retries=0)
            sim_store.execute(run["id"],graph,objective,llm=model)
        except Exception as exc:
            # Error codes only, never leak evidence or model prompts.
            state=sim_store.get(run["id"])
            if state and state["state"] in ("queued","running"):
                sim_store._update(run["id"],state="failed",error_code=type(exc).__name__[:64])
        finally:
            if model is not None:
                model.client.close()
    threading.Thread(target=worker,daemon=True,
                     name="native-sim-"+run["id"][-6:]).start()
    return jsonify({"success":True,"data":{
        "simulation_id":run["id"],"project_id":project_id,"status":"queued",
        "mode":mode,"message":"Simulación local iniciada con límites de recursos"
    }}),202


@native_sim_bp.get("/project/<project_id>/latest")
def latest(project_id):
    project=_project_readable(project_id)
    if not project:
        return jsonify({"success":False,"error":"Proyecto no disponible"}),404
    run=_store().latest(project_id)
    return jsonify({"success":True,"data":_store().public(run["id"]) if run else None})


@native_sim_bp.get("/<run_id>")
def read(run_id):
    owned=_get_owned_run(run_id)
    if not owned:
        return jsonify({"success":False,"error":"Simulación no disponible"}),404
    return jsonify({"success":True,"data":_store().public(run_id)})


@native_sim_bp.post("/<run_id>/feedback")
def submit_feedback(run_id):
    owned=_get_owned_run(run_id)
    if not owned:
        return jsonify({"success":False,"error":"Simulación no disponible"}),404
    data=request.get_json(silent=True) or {}
    try:
        _store().feedback(run_id,actor_uuid=data.get("actor_uuid",""),
                         phase=data.get("phase"),verdict=data.get("verdict",""),
                         note=data.get("note",""))
    except (ValueError,KeyError):
        return jsonify({"success":False,"error":"La retroalimentación no es válida"}),422
    return jsonify({"success":True,"data":{"feedback":_store().quality(run_id),
                                          "method":"human_review_no_autonomous_retraining"}})


@native_sim_bp.get("/<run_id>/report.md")
def download_report(run_id):
    owned=_get_owned_run(run_id)
    if not owned:
        return jsonify({"success":False,"error":"Simulación no disponible"}),404
    data=_store().public(run_id)
    report=data.get("report")
    if not report:
        return jsonify({"success":False,"error":"El informe aún no está listo"}),409
    text=[
        "# "+report["title"],"",
        "**Alcance:** escenario hipotético, sin afirmaciones de incidentes reales.","",
        "**Proyecto:** "+owned["project_id"],
        "**Grafo:** "+owned["graph_id"],
        "**Objetivo:** "+report["scenario_goal"],"",
        "## Resultados",
        "- Participantes: "+", ".join(report["roles"]),
        "- Acciones hipotéticas: "+str(report["actions"]),
        "- Cobertura de evidencias: "+str(report["evidence_coverage_pct"])+"%",
        "- Llamadas a IA externa: 0",
        "- Planificador: "+report["plan"]["basis"],"",
        "## Decisiones de dirección"
    ]+[f"- {x}" for x in report["decisions_required"]]+[
        "","## Acciones simuladas (no ejecutadas)"
    ]+[f"- Ronda {a['phase']} · {a['actor_type']}: {a['action_text']} (Fuente: {a['evidence_source']})"
       for a in data["actions"]]+["","## Limitaciones",report["disclaimer"],
                                   "No equivale al entorno OASIS anterior ni a una prueba de seguridad real."]
    response=Response("\n".join(text)+"\n",mimetype="text/markdown; charset=utf-8")
    response.headers["Content-Disposition"]=f'attachment; filename="simulacion-{run_id}.md"'
    response.headers["Cache-Control"]="no-store"
    return response
