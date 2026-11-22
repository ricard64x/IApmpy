#!/usr/bin/env python3
"""Comparación A/B pareada con etiquetas de referencia independientes.

Entrada: JSON {
  "dataset_id":"evaluacion_...","label_source":"expertos_independientes",
  "cases":[{"case_id":"c01","gold":["doc:1"],"baseline":["doc:2"],
            "candidate":["doc:1"],"baseline_latency_ms":100,
            "candidate_latency_ms":70, "baseline_tokens":800,
            "candidate_tokens":600}]
}
No mide si una simulación predice correctamente: mide RECUPERACIÓN documental.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def _rank_metrics(retrieved, gold, k):
    top = retrieved[:k]
    relevant = set(gold)
    hits = sum(1 for doc in top if doc in relevant)
    reciprocal_rank = next((1 / (i + 1) for i, doc in enumerate(top)
                            if doc in relevant), 0)
    return {
        "precision_at_k": hits / len(top) if top else 0.0,
        "recall_at_k": hits / len(relevant),
        "reciprocal_rank": reciprocal_rank,
    }


def _p95(vals):
    if not vals:
        return None
    ordered = sorted(vals)
    return round(ordered[math.ceil(len(ordered)*.95) - 1], 2)


def compare(dataset, *, min_cases=12, k=5):
    if not isinstance(dataset, dict) or not dataset.get("dataset_id") \
       or dataset.get("label_source") not in ("experts_independent", "expertos_independientes"):
        raise ValueError("Falta el origen independiente de las etiquetas de referencia.")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) < min_cases:
        raise ValueError(f"Se requieren al menos {min_cases} casos comparables.")
    scores = {"baseline": [], "candidate": []}
    latencies = {"baseline": [], "candidate": []}
    tokens = {"baseline": [], "candidate": []}
    case_ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise ValueError("Caso sin identificador.")
        if case["case_id"] in case_ids:
            raise ValueError("Caso de evaluación duplicado.")
        case_ids.add(case["case_id"])
        gold = case.get("gold")
        if not isinstance(gold, list) or not gold or any(type(x) is not str for x in gold):
            raise ValueError("Se necesitan fuentes de referencia verificadas para cada caso.")
        for variant in scores:
            retrieved = case.get(variant)
            if not isinstance(retrieved, list) or any(type(x) is not str for x in retrieved):
                raise ValueError("Ambas variantes deben registrar la búsqueda realizada.")
            scores[variant].append(_rank_metrics(retrieved, gold, k))
            timing = case.get(f"{variant}_latency_ms")
            if isinstance(timing, (int,float)) and math.isfinite(timing) and timing >= 0:
                latencies[variant].append(float(timing))
            token_count = case.get(f"{variant}_tokens")
            if type(token_count) is int and token_count >= 0:
                tokens[variant].append(token_count)
    def average(name, key):
        return round(statistics.mean(x[key] for x in scores[name]), 4)
    result = {
        "dataset_id": dataset["dataset_id"], "source": dataset["label_source"],
        "sample_count": len(cases), "top_k": k,
        "baseline": {}, "candidate": {}, "delta": {},
        "disclaimer": "Precisión de RECUPERACIÓN documental, no exactitud de predicciones.",
    }
    for name in scores:
        result[name] = {
            "precision_at_k": average(name, "precision_at_k"),
            "recall_at_k": average(name, "recall_at_k"),
            "mrr": average(name, "reciprocal_rank"),
            "latency_p95_ms": _p95(latencies[name]) if len(latencies[name]) == len(cases) else None,
            "tokens_total_observed": sum(tokens[name]) if len(tokens[name]) == len(cases) else None,
        }
    for key in ("precision_at_k","recall_at_k","mrr"):
        result["delta"][key] = round(result["candidate"][key] - result["baseline"][key],4)
    if result["baseline"]["latency_p95_ms"] is not None and result["candidate"]["latency_p95_ms"] is not None:
        result["delta"]["latency_p95_ms"] = round(result["candidate"]["latency_p95_ms"] -
                                                    result["baseline"]["latency_p95_ms"],2)
    else:
        result["delta"]["latency_p95_ms"] = None
    old = result["baseline"]["tokens_total_observed"]
    new = result["candidate"]["tokens_total_observed"]
    result["delta"]["token_reduction_percent"] = round(100*(old-new)/old,2) if old and new is not None else None
    # Establish this threshold BEFORE seeing real outcomes in a study plan.
    result["retrieval_non_regression_gate"] = (
        result["candidate"]["recall_at_k"] >= result["baseline"]["recall_at_k"] - .03
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--min-cases",type=int,default=12)
    args=parser.parse_args()
    with args.dataset.open(encoding="utf-8") as f:
        dataset=json.load(f)
    result=compare(dataset,min_cases=args.min_cases)
    payload=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(payload+"\n",encoding="utf-8")
    else:
        print(payload)
    if not result["retrieval_non_regression_gate"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
