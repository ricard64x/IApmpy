"""Conservative OASIS capacity admission control for one 2 GiB Fly Machine."""
import os
import threading
from .config import Config
from pathlib import Path
from flask import Blueprint, g, jsonify, request
from .services.simulation_manager import SimulationManager
from .services.simulation_runner import SimulationRunner, RunnerStatus

capacity_bp = Blueprint("capacity", __name__)
_start_lock = threading.Lock()

def _read_positive(path):
    try:
        val = int(Path(path).read_text().strip())
        return val if 0 < val < (1 << 45) else None
    except (ValueError, OSError):
        return None

def runtime_capacity():
    # Cgroup memory limits supersede deployment configuration when available.
    v2 = _read_positive("/sys/fs/cgroup/memory.max")
    v1 = _read_positive("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    configured = max(512, int(os.environ.get("OASIS_MACHINE_MEMORY_MB", "2048")))
    memory_mb = min(configured, int(min(x for x in (v1, v2) if x) / 1048576)) if (v1 or v2) else configured
    used = _read_positive("/sys/fs/cgroup/memory.current") or _read_positive(
        "/sys/fs/cgroup/memory/memory.usage_in_bytes"
    )
    used_mb = round(used / 1048576) if used else None
    # Validated for 45 loaded profiles, 2 active agents per platform and 10
    # rounds on one 2048 MiB Fly Machine using OASIS random recommendations.
    limits = {512: 8, 1024: 20, 1536: 30, 2048: 45}
    cap = min((limit for size, limit in limits.items() if memory_mb <= size), default=45)
    cap = min(cap, int(os.environ.get("OASIS_MAX_PROFILES", "45")))
    max_active = max(1, min(2, int(os.environ.get("OASIS_MAX_ACTIVE_AGENTS_PER_ROUND", "2"))))
    busy = False
    for sim in SimulationManager().list_simulations():
        run = SimulationRunner.get_run_state(sim.simulation_id)
        if run and run.runner_status in (RunnerStatus.RUNNING, RunnerStatus.PAUSED, RunnerStatus.STOPPING):
            busy = True
            break
    try:
        disk = os.statvfs(Config.UPLOAD_FOLDER)
        disk_total_mb = round(disk.f_blocks * disk.f_frsize / 1048576)
        disk_free_mb = round(disk.f_bavail * disk.f_frsize / 1048576)
    except OSError:
        disk_total_mb, disk_free_mb = None, None
    return {
        "storage_total_mb": disk_total_mb,
        "storage_free_mb": disk_free_mb,
        "machine_memory_mb": memory_mb,
        "memory_used_mb": used_mb,
        "memory_free_estimate_mb": max(0, memory_mb - used_mb) if used_mb is not None else None,
        "recommended_max_profiles": cap,
        "max_active_agents_per_platform_per_round": max_active,
        "maximum_parallel_simulations": 1,
        "recommended_max_rounds": 10,
        "busy": busy,
        "recommendation_mode": os.environ.get("OASIS_TWITTER_RECSYS", "random"),
        "note": (
            "Límite operativo conservador, no garantía de capacidad universal. "
            "En 2 GB se validaron 45 perfiles, 2 agentes activos por plataforma y 10 rondas. "
            "La demanda real depende de agentes, rondas y modelo."
        ),
    }

@capacity_bp.get("/status")
def status():
    return jsonify({"success": True, "data": runtime_capacity()})

def install_capacity(app):
    app.register_blueprint(capacity_bp, url_prefix="/api/capacity")

    @app.before_request
    def protect_storage_capacity():
        if request.path != "/api/graph/ontology/generate" or request.method != "POST":
            return None
        info = runtime_capacity()
        content_mb = round((request.content_length or 0) / 1048576)
        if info["storage_free_mb"] is not None and info["storage_free_mb"] < 100 + content_mb:
            return jsonify({
                "success": False,
                "error": "El almacenamiento está casi lleno. Liberá espacio antes de cargar documentos.",
            }), 507

    @app.before_request
    def protect_simulation_start():
        if request.path != "/api/simulation/start" or request.method != "POST":
            return None
        if not _start_lock.acquire(blocking=False):
            return jsonify({"success": False, "error": "Hay otro inicio de simulación en curso."}), 409
        g.tenondera_start_lock = True
        info = runtime_capacity()
        if info["busy"]:
            return jsonify({"success": False, "error": "Ya existe una simulación activa. Esperá a que termine."}), 409
        if (info["memory_used_mb"] is not None
                and info["memory_used_mb"] > info["machine_memory_mb"] * 0.80):
            return jsonify({"success": False, "error": "Memoria insuficiente en este momento."}), 503
        payload = request.get_json(silent=True) or {}
        rounds = payload.get("max_rounds")
        if rounds is not None:
            try:
                if isinstance(rounds, bool) or int(rounds) > 10 or int(rounds) < 1:
                    return jsonify({"success": False, "error": "En esta máquina se permiten entre 1 y 10 rondas por ejecución."}), 422
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "Cantidad de rondas inválida."}), 422
        simulation_id = payload.get("simulation_id")
        if not isinstance(simulation_id, str):
            return None
        config = SimulationManager().get_simulation_config(simulation_id)
        if isinstance(config, dict):
            profiles = config.get("agent_configs") or []
            if len(profiles) > info["recommended_max_profiles"]:
                return jsonify({
                    "success": False,
                    "error": (
                        f"El escenario contiene {len(profiles)} perfiles. "
                        f"Máximo configurado: {info['recommended_max_profiles']} "
                        f"con {info['machine_memory_mb']} MB."
                    ),
                    "capacity": info,
                }), 422
        return None

    @app.after_request
    def unlock_simulation_start(response):
        if getattr(g, "tenondera_start_lock", False):
            _start_lock.release()
            g.tenondera_start_lock = False
        return response
