#!/usr/bin/env python3
"""Exactitud DE DECISIONES con etiquetas independientes, no un juez LLM.

El gold-set debe provenir de evaluación humana o desenlace comprobado. Cada
escenario debe tener clasificación base/candidato sobre EL MISMO caso.
Se niega a puntuar con una sola clase o muestras insuficientes.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


def _scores(actual, predicted):
    tp=sum(a and p for a,p in zip(actual,predicted))
    tn=sum(not a and not p for a,p in zip(actual,predicted))
    fp=sum(not a and p for a,p in zip(actual,predicted))
    fn=sum(a and not p for a,p in zip(actual,predicted))
    precision=tp/(tp+fp) if tp+fp else None
    sensitivity=tp/(tp+fn) if tp+fn else None
    specificity=tn/(tn+fp) if tn+fp else None
    accuracy=(tp+tn)/len(actual)
    balanced=(sensitivity+specificity)/2 if sensitivity is not None and specificity is not None else None
    return {
        "tp":tp,"tn":tn,"fp":fp,"fn":fn,
        "accuracy":round(accuracy,4),
        "balanced_accuracy":round(balanced,4) if balanced is not None else None,
        "precision":round(precision,4) if precision is not None else None,
        "recall":round(sensitivity,4) if sensitivity is not None else None,
        "specificity":round(specificity,4) if specificity is not None else None,
        "false_positive_rate":round(fp/(tn+fp),4),
        "false_negative_rate":round(fn/(tp+fn),4),
    }


def evaluate(data, minimum=20):
    if not isinstance(data,dict) or data.get("label_source") not in (
        "expertos_independientes","desenlace_comprobado","experts_independent","verified_outcome"
    ):
        raise ValueError("El resultado real debe tener fuente independiente del modelo.")
    cases=data.get("cases")
    if not isinstance(cases,list) or len(cases)<minimum:
        raise ValueError(f"Necesitás al menos {minimum} casos adjudicados.")
    ids=set()
    actual=[]
    predicted={"baseline":[],"candidate":[]}
    probability={"baseline":[],"candidate":[]}
    for c in cases:
        if not isinstance(c,dict) or not isinstance(c.get("case_id"),str) \
            or c["case_id"] in ids or type(c.get("actual")) is not bool:
            raise ValueError("Casos sin ID único o sin desenlace comprobado booleano.")
        ids.add(c["case_id"])
        actual.append(c["actual"])
        for model in predicted:
            if type(c.get(model)) is not bool:
                raise ValueError("Faltan decisiones binarias comparables.")
            predicted[model].append(c[model])
            p=c.get(f"{model}_probability")
            if type(p) in (float,int) and math.isfinite(p) and 0<=p<=1:
                probability[model].append(float(p))
    if len(set(actual))<2:
        raise ValueError("Se necesitan casos positivos y negativos.")
    scores={key:_scores(actual,vals) for key,vals in predicted.items()}
    for key in scores:
        probs=probability[key]
        scores[key]["brier_score"]=round(sum((p-int(y))**2 for p,y in zip(probs,actual))/len(actual),4) \
            if len(probs)==len(actual) else None
    return {
        "dataset_id":data.get("dataset_id"),"source":data["label_source"],
        "cases":len(actual),"positive_cases":sum(actual),"negative_cases":len(actual)-sum(actual),
        "baseline":scores["baseline"],"candidate":scores["candidate"],
        "delta_balanced_accuracy":round(
            scores["candidate"]["balanced_accuracy"]-scores["baseline"]["balanced_accuracy"],4
        ),
        "non_regression_gate":(
            scores["candidate"]["balanced_accuracy"]>=scores["baseline"]["balanced_accuracy"]
            and scores["candidate"]["false_negative_rate"]<=scores["baseline"]["false_negative_rate"]
        ),
        "methodology":"Exactitud solo para casos adjudicados, no tasa universal de predicción.",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("dataset",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    with args.dataset.open(encoding="utf-8") as f:data=json.load(f)
    output=evaluate(data)
    text=json.dumps(output,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(text+"\n",encoding="utf-8")
    else:print(text)
    if not output["non_regression_gate"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
