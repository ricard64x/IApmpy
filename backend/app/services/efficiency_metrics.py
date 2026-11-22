"""Indicadores reproducibles de una simulación; nunca inventa ahorros ni precisión.

Se calculan sobre datos de ejecución guardados, con límites de lectura.
Los indicadores estructurales NO equivalen a exactitud de predicciones.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import statistics
from pathlib import Path

from ..config import Config

_SIM = re.compile(r"^sim_[A-Za-z0-9_-]{2,90}$")


def _tail_jsonl(path: Path, cap=1024 * 1024):
    if not path.is_file():
        return []
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > cap:
            f.seek(-cap, os.SEEK_END)
            f.readline()  # drop a potentially incomplete first record
        raw = f.read(cap)
    rows = []
    for line in raw.splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except (TypeError, ValueError):
            continue
    return rows


def _p(values, percentage):
    if not values:
        return None
    data = sorted(values)
    return round(data[min(len(data) - 1, math.ceil(len(data) * percentage) - 1)], 2)


def _actual_int(row, field):
    val = row.get(field)
    return val if type(val) is int and val >= 0 else None


def _model_prices():
    first = os.getenv("LLM_PRICE_INPUT_PER_1M_USD")
    second = os.getenv("LLM_PRICE_OUTPUT_PER_1M_USD")
    if first is None or second is None:
        return None
    try:
        values = (float(first), float(second))
        if not all(math.isfinite(p) and p >= 0 for p in values):
            return None
        return values
    except (ValueError, TypeError):
        return None


def get_simulation_efficiency(simulation_id: str):
    if not isinstance(simulation_id, str) or not _SIM.fullmatch(simulation_id):
        raise ValueError("Identificador de simulación inválido.")
    root = Path(Config.UPLOAD_FOLDER) / "simulations" / simulation_id
    if not (root / "state.json").is_file():
        raise FileNotFoundError("No existe un expediente de simulación.")
    requests = _tail_jsonl(root / "llm_usage_metrics.jsonl")
    memory = _tail_jsonl(root / "getangiru_metrics.jsonl")
    system = _tail_jsonl(root / "lightweight_metrics.jsonl")
    actions = sum(
        (_tail_jsonl(root / p / "actions.jsonl") for p in ("twitter", "reddit")), []
    )
    observations = [x for x in actions
                    if x.get("action_type") == "CREATE_POST"
                    and x.get("source_mode") == "sintetico_gpt_liviano"]
    unique_ids = set()
    seen_text = set()
    repeated = 0
    for item in observations:
        ident = item.get("agent_id")
        if type(ident) is int:
            unique_ids.add(ident)
        args = item.get("action_args")
        text = args.get("content", "") if isinstance(args, dict) else ""
        clean = " ".join(str(text).lower().split())
        if clean in seen_text:
            repeated += 1
        if clean:
            seen_text.add(clean)
    profile_count = None
    known_profile_ids = None
    profiles = root / "reddit_profiles.json"
    if profiles.is_file():
        try:
            with profiles.open(encoding="utf-8") as f:
                profile_list = json.load(f)
            if isinstance(profile_list, list):
                profile_count = len(profile_list)
                known_profile_ids = set()
                for i, profile in enumerate(profile_list):
                    if isinstance(profile, dict):
                        try:
                            known_profile_ids.add(int(profile.get("user_id", i)))
                        except (TypeError, ValueError):
                            pass
        except (OSError, ValueError):
            pass
    elif (root / "twitter_profiles.csv").is_file():
        try:
            with (root / "twitter_profiles.csv").open(encoding="utf-8-sig", newline="") as f:
                raw_profiles = list(csv.DictReader(f))
            profile_count = len(raw_profiles)
            known_profile_ids = set()
            for i, profile in enumerate(raw_profiles):
                try:
                    known_profile_ids.add(int(profile.get("user_id") or i))
                except (TypeError, ValueError):
                    pass
        except OSError:
            pass

    valid_profiles_with_actions = len(unique_ids & known_profile_ids) if known_profile_ids is not None else len(unique_ids)
    unexpected_profiles_with_actions = len(unique_ids - known_profile_ids) if known_profile_ids is not None else None

    valid_tokens = [x for x in requests if _actual_int(x, "actual_prompt_tokens") is not None
                    and _actual_int(x, "actual_completion_tokens") is not None]
    observed_input = sum(_actual_int(r, "actual_prompt_tokens") for r in valid_tokens)
    observed_output = sum(_actual_int(r, "actual_completion_tokens") for r in valid_tokens)
    prices = _model_prices()
    cost = round((observed_input * prices[0] + observed_output * prices[1]) / 1e6, 6) \
        if prices and len(valid_tokens) == len(requests) and requests else None
    latencies = [float(x["latency_ms"]) for x in requests
                 if isinstance(x.get("latency_ms"), (int, float))
                 and math.isfinite(float(x["latency_ms"])) and x["latency_ms"] >= 0]
    memory_latency = [float(x["latency_ms"]) for x in memory
                      if isinstance(x.get("latency_ms"), (int, float))
                      and math.isfinite(float(x["latency_ms"])) and x["latency_ms"] >= 0]
    peak_kib = [x["maxrss_kib"] for x in system
                if isinstance(x.get("maxrss_kib"), (int, float)) and x["maxrss_kib"] >= 0]
    returned_from_memory = sum(max(0, int(r.get("retrieved_sources") or 0)) for r in requests)
    return {
        "simulation_id": simulation_id,
        "source": "Registros locales de ejecución (no estimación)",
        "model": {
            "calls": len(requests),
            "successful_calls": sum(x.get("status") == "ok" for x in requests),
            "provider_attempts": sum(_actual_int(x, "provider_attempts") or 0 for x in requests),
            "actual_token_calls": len(valid_tokens),
            "input_tokens_actual": observed_input if valid_tokens else None,
            "output_tokens_actual": observed_output if valid_tokens else None,
            "cost_usd_actual_from_configured_prices": cost,
            "latency_p50_ms": _p(latencies, 0.50),
            "latency_p95_ms": _p(latencies, 0.95),
        },
        "memory": {
            "queries": len(memory),
            "success": sum(x.get("status") in ("ok", "cache") for x in memory),
            "cache_hits": sum(x.get("cache_hit") is True for x in memory),
            "unavailable": sum(x.get("status") not in ("ok", "cache") for x in memory),
            "p50_ms": _p(memory_latency, 0.5),
            "p95_ms": _p(memory_latency, 0.95),
            "validated_sources_used": returned_from_memory,
        },
        "quality_structural": {
            "expected_profiles": profile_count,
            "unique_profiles_with_actions": valid_profiles_with_actions,
            "unexpected_profile_ids": unexpected_profiles_with_actions,
            "profile_coverage_percent": round(100 * valid_profiles_with_actions / profile_count, 2)
            if profile_count else None,
            "synthetic_actions": len(observations),
            "duplicated_text_actions": repeated,
            "duplicated_text_percent": round(100 * repeated / len(observations), 2)
            if observations else None,
            "factual_accuracy_percent": None,
            "factual_accuracy_reason": "Requiere casos reales anonimizados y resultados de referencia independientes.",
        },
        "resource": {
            "peak_child_process_rss_mb": round(max(peak_kib) / 1024, 2) if peak_kib else None,
            "last_elapsed_seconds": system[-1].get("elapsed_seconds") if system else None,
        },
        "comparability": {
            "savings_percent": None,
            "reason": "No existe un experimento A/B controlado con el mismo conjunto de casos.",
        },
    }
