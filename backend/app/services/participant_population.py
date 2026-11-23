"""Operator-controlled simulation population, never evidence of real people.

A prepared profile is an input to a synthetic simulation.  Additional profiles
are labelled generic hypothetical roles, NOT graph entities or survey respondents.
The original prepared population is kept as an immutable baseline in the new
version. No prior run logs are modified.
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

MAX_LITE = 120  # Same bound as scripts.run_lightweight_simulation.MAX_PEOPLE
MAX_OASIS_2GB = 12  # Conservative operator cap; not a RAM guarantee
_ROLES = (
    ("Cliente cauteloso", "Solicita garantías, detalles claros y evita compromisos apresurados.", "skeptical"),
    ("Analista financiero", "Compara costos totales, alternativas y supuestos del presupuesto.", "neutral"),
    ("Especialista en riesgos", "Identifica escenarios adversos y controles verificables.", "skeptical"),
    ("Usuario práctico", "Prioriza facilidad de uso, claridad y resultados concretos.", "neutral"),
    ("Evaluador de proveedores", "Contrasta entregables, experiencia, referencias y niveles de servicio.", "neutral"),
    ("Representante comercial", "Expone condiciones, beneficios y limitaciones de las propuestas.", "supportive"),
    ("Observador independiente", "Cuestiona supuestos y pide pruebas antes de opinar.", "observer"),
    ("Especialista técnico", "Analiza factibilidad, mantenimiento y dependencia tecnológica.", "neutral"),
    ("Responsable de cumplimiento", "Revisa compromisos, privacidad y obligaciones regulatorias.", "skeptical"),
    ("Administrador operativo", "Evalúa tiempos, capacidad, soporte y continuidad del servicio.", "neutral"),
)
_ID = re.compile(r"^sim_[A-Za-z0-9_-]{1,90}$")


def capacity_limit(engine_mode: str) -> int:
    if engine_mode == "lightweight":
        return MAX_LITE
    if engine_mode == "oasis":
        return MAX_OASIS_2GB
    raise ValueError("Motor de simulación inválido.")


def _read_profiles(directory: Path):
    reddit = directory / "reddit_profiles.json"
    twitter = directory / "twitter_profiles.csv"
    if reddit.is_file():
        data = json.loads(reddit.read_text(encoding="utf-8"))
    elif twitter.is_file():
        with twitter.open(encoding="utf-8-sig", newline="") as handle:
            data = list(csv.DictReader(handle))
    else:
        raise ValueError("No hay perfiles preparados para esta simulación.")
    if not isinstance(data, list) or not data or not all(isinstance(p, dict) for p in data):
        raise ValueError("Los perfiles preparados no son válidos.")
    seen = set()
    for index, p in enumerate(data):
        try:
            identifier = int(p.get("user_id", index))
        except (ValueError, TypeError):
            raise ValueError("Identificador de perfil inválido.")
        if identifier < 0 or identifier in seen:
            raise ValueError("Identificadores de perfiles inválidos o duplicados.")
        seen.add(identifier)
    return data


def _baseline(directory: Path):
    path = directory / "population_base.json"
    if path.is_file():
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or not isinstance(obj.get("profiles"), list) or not obj["profiles"]:
            raise ValueError("La base original de participantes no es válida.")
        return obj
    config_file = directory / "simulation_config.json"
    if not config_file.is_file():
        raise ValueError("No hay configuración preparada para esta simulación.")
    config = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Configuración original inválida.")
    return {"profiles": _read_profiles(directory), "config": config}


def population_status(directory: Path, engine_mode: str = "lightweight") -> dict:
    baseline = _baseline(directory)
    current = _read_profiles(directory)
    original_count = len(baseline["profiles"])
    return {
        "detected_profiles": original_count,
        "selected_participants": len(current),
        "synthetic_additions": max(0, len(current) - original_count),
        "max_lightweight": MAX_LITE,
        "max_oasis": min(MAX_OASIS_2GB, original_count),
        "maximum_for_engine": MAX_LITE if engine_mode == "lightweight" else min(MAX_OASIS_2GB, original_count),
        "synthetic_participants_not_graph_entities": True,
    }


def _atomic_text(path: Path, content: str):
    temp = path.with_name(path.name + ".population.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def resize_population(directory: Path, requested: int, engine_mode: str) -> dict:
    if not isinstance(requested, int) or isinstance(requested, bool):
        raise ValueError("La cantidad de participantes debe ser un número entero.")
    directory = Path(directory)
    base = _baseline(directory)
    existing = base["profiles"]
    detected = len(existing)
    maximum = MAX_LITE if engine_mode == "lightweight" else min(MAX_OASIS_2GB, detected)
    if requested < 2 or requested > maximum:
        raise ValueError(f"Seleccioná entre 2 y {maximum} participantes para este motor.")
    if detected > 500:
        raise ValueError("Cantidad de perfiles detectados fuera del límite seguro.")
    if not isinstance(base.get("config"), dict):
        raise ValueError("Configuración de perfiles original inválida.")
    original_configs = {
        int(x["agent_id"]): x for x in base["config"].get("agent_configs", [])
        if isinstance(x, dict) and isinstance(x.get("agent_id"), int)
    }
    active = []
    configs = []
    manifest = []
    # Deterministic ordering and contiguous 0-based IDs required by OASIS.
    for index in range(requested):
        if index < detected:
            p = dict(existing[index])
            old_id = int(p.get("user_id", index))
            origin = "grafo_preparado"
            cfg = dict(original_configs.get(old_id) or {})
            name = str(p.get("name") or p.get("username") or f"Perfil {index + 1}")[:110]
        else:
            role, viewpoint, stance = _ROLES[(index - detected) % len(_ROLES)]
            name = f"Perfil sintético {index + 1} — {role}"
            p = {
                "name": name,
                "username": f"simulado_{index + 1}",
                "bio": "Rol hipotético adicional; no es persona ni entidad del grafo.",
                "persona": ("Rol de prueba generado por solicitud del usuario. " + viewpoint +
                            " Debatir el escenario únicamente como hipótesis, "
                            "sin suplantar personas reales ni afirmar experiencias propias."),
                "age": 30, "gender": "other", "mbti": "ISTJ",
                "country": "Paraguay", "karma": 1000,
            }
            origin = "rol_sintetico_adicional"
            cfg = {
                "entity_uuid": "", "entity_type": "SyntheticRole", "entity_name": name,
                "activity_level": 0.6, "posts_per_hour": 0.4, "comments_per_hour": 0.9,
                "active_hours": list(range(8, 23)),
                "response_delay_min": 5, "response_delay_max": 45,
                "sentiment_bias": 0, "stance": stance, "influence_weight": 1.0,
            }
        p["user_id"] = index
        # Preserve genuine profile details while guaranteeing a clear identity.
        p["name"] = name
        p["username"] = str(p.get("username") or f"perfil_{index + 1}")[:70]
        p["persona"] = str(p.get("persona") or p.get("user_char") or p.get("bio") or name)[:4000]
        p["bio"] = str(p.get("bio") or p.get("description") or name)[:150]
        active.append(p)
        cfg["agent_id"] = index
        cfg.setdefault("entity_uuid", "")
        cfg.setdefault("entity_name", name)
        cfg.setdefault("entity_type", "Unknown")
        cfg.setdefault("activity_level", 0.5)
        cfg.setdefault("posts_per_hour", 0.5)
        cfg.setdefault("comments_per_hour", 1.0)
        cfg.setdefault("active_hours", list(range(8, 23)))
        cfg.setdefault("response_delay_min", 5)
        cfg.setdefault("response_delay_max", 60)
        cfg.setdefault("sentiment_bias", 0.0)
        cfg.setdefault("stance", "neutral")
        cfg.setdefault("influence_weight", 1.0)
        configs.append(cfg)
        manifest.append({"agent_id": index, "origin": origin, "name": name})
    config = json.loads(json.dumps(base["config"], ensure_ascii=False))
    config["simulation_id"] = directory.name
    config["agent_configs"] = configs
    # Initial events may not refer to identities excluded by the user.
    events = config.get("event_config")
    if isinstance(events, dict) and isinstance(events.get("initial_posts"), list):
        for idx, post in enumerate(events["initial_posts"]):
            if isinstance(post, dict):
                original_id = post.get("poster_agent_id")
                lookup = {int(p.get("user_id", i)): i for i,p in enumerate(existing[:requested])}
                post["poster_agent_id"] = lookup.get(original_id, idx % requested)
    clock = config.get("time_config")
    if isinstance(clock, dict):
        clock["agents_per_hour_min"] = min(requested, max(1, int(clock.get("agents_per_hour_min") or 1)))
        clock["agents_per_hour_max"] = min(requested, max(1, int(clock.get("agents_per_hour_max") or requested)))
    config["population_metadata"] = {
        "detected_profiles": detected,
        "selected_participants": requested,
        "synthetic_additions": max(0, requested - detected),
        "origin": "operator_selected",
        "synthetic_only": True,
        "note": "Los personajes adicionales no provienen del grafo y no representan personas reales.",
    }
    twitter_lines = []
    import io
    sio = io.StringIO(newline="")
    writer = csv.DictWriter(sio, fieldnames=["user_id","name","username","user_char","description"])
    writer.writeheader()
    for p in active:
        writer.writerow({
            "user_id": p["user_id"], "name": p["name"], "username": p["username"],
            "user_char": p["persona"].replace("\n", " "),
            "description": p["bio"].replace("\n", " "),
        })
    # Store source baseline before altering the prepared working files.
    if not (directory / "population_base.json").exists():
        _atomic_text(directory / "population_base.json", json.dumps(base, ensure_ascii=False, indent=2))
    # Keep one writer and readable complete files, without touching run logs.
    _atomic_text(directory / "reddit_profiles.json", json.dumps(active, ensure_ascii=False, indent=2))
    _atomic_text(directory / "twitter_profiles.csv", sio.getvalue())
    _atomic_text(directory / "simulation_config.json", json.dumps(config, ensure_ascii=False, indent=2))
    _atomic_text(directory / "population_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return population_status(directory, engine_mode)
