"""Per-simulation execution options and truthful, persisted finalization phases.

A simulation can run in one supported social environment or both.  Settings
are stored beside the simulation on the persistent volume and cannot change
once an execution has started.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..config import Config

_VALID_ID = re.compile(r"^sim_[A-Za-z0-9_-]{1,90}$")
_PLATFORMS = ("twitter", "reddit", "parallel")
_DEFAULTS = {"platform": "parallel", "auto_finalize": True, "max_rounds": 10}


def settings_path(simulation_id: str) -> Path:
    if not isinstance(simulation_id, str) or not _VALID_ID.fullmatch(simulation_id):
        raise ValueError("Identificador de simulación inválido.")
    return Path(Config.UPLOAD_FOLDER) / "simulations" / simulation_id / "execution_settings.json"


def get_execution_settings(simulation_id: str) -> dict:
    path = settings_path(simulation_id)
    if not path.is_file():
        return dict(_DEFAULTS)
    with path.open(encoding="utf-8") as handle:
        stored = json.load(handle)
    return {**_DEFAULTS, **{k: stored[k] for k in _DEFAULTS if k in stored}}


def validate_execution_settings(body: dict) -> dict:
    if not isinstance(body, dict):
        raise ValueError("Configuración inválida.")
    platform = body.get("platform", "parallel")
    if platform not in _PLATFORMS:
        raise ValueError("Elegí Plaza, Comunidad o ambas.")
    auto_finalize = body.get("auto_finalize", True)
    if type(auto_finalize) is not bool:
        raise ValueError("El cierre automático debe ser verdadero o falso.")
    rounds = body.get("max_rounds", 10)
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 10:
        raise ValueError("Seleccioná entre 1 y 10 rondas.")
    return {"platform": platform, "auto_finalize": auto_finalize, "max_rounds": rounds}


def save_execution_settings(simulation_id: str, body: dict) -> dict:
    path = settings_path(simulation_id)
    if not path.parent.is_dir():
        raise ValueError("La simulación no existe.")
    settings = validate_execution_settings(body)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return settings


def execution_progress(run: dict, settings: dict | None = None) -> dict:
    """Return a derived UI phase; never relabel the actual runner status.

    Completion is signaled by simulation_end events from every *selected*
    platform, not just the numerical round counter. Only a terminal runner
    state can unlock the report.
    """
    opts = settings or _DEFAULTS
    mode = run.get("platform_mode") or opts.get("platform", "parallel")
    if mode not in _PLATFORMS:
        mode = "parallel"
    enabled = ["twitter", "reddit"] if mode == "parallel" else [mode]
    total = max(0, int(run.get("total_rounds") or 0))
    rounds = {p: max(0, int(run.get(f"{p}_current_round") or 0)) for p in enabled}
    complete = total > 0 and all(
        bool(run.get(f"{p}_completed")) and rounds[p] >= total for p in enabled
    )
    terminal = run.get("runner_status") or "idle"
    auto_finalize = run.get("auto_finalize")
    if auto_finalize is None:
        # Existing runs started before these settings were introduced were
        # launched in wait-for-command mode.
        auto_finalize = False
    finalizing_requested = bool(run.get("finalizing_requested"))
    if terminal == "failed":
        phase = "failed"
    elif terminal in ("completed", "stopped"):
        phase = "completed" if terminal == "completed" else "stopped"
    elif terminal == "stopping" or finalizing_requested or (complete and auto_finalize):
        phase = "finalizing"
    elif complete and terminal == "running":
        phase = "awaiting_close"
    elif terminal in ("running", "starting", "paused"):
        phase = "running_rounds"
    else:
        phase = "idle"
    round_fraction = sum(min(rounds[p], total) for p in enabled) / (total * len(enabled)) if total else 0
    progress = 100 if phase == "completed" or (phase == "stopped" and complete) else (
        95 if phase == "finalizing" else
        90 if phase == "awaiting_close" else round(round_fraction * 85)
    )
    return {
        "phase": phase,
        "platform_mode": mode,
        "enabled_platforms": enabled,
        "auto_finalize": bool(auto_finalize),
        "all_rounds_completed": complete,
        "finalizing_requested": finalizing_requested,
        "can_close_env": phase == "awaiting_close",
        "can_generate_report": terminal in ("completed", "stopped"),
        "lifecycle_progress_percent": progress,
    }
