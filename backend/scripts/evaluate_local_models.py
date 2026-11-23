#!/usr/bin/env python3
"""Evaluate two locally served model aliases using human-approved holdout data.

This CLI NEVER promotes a candidate. It only saves an aggregate signed-off
decision for release management. It refuses external URLs by construction.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from app.services.model_evaluation import approved_cases,evaluate,gate

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--approved-holdout",required=True)
    p.add_argument("--baseline",required=True)
    p.add_argument("--candidate",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    if args.baseline==args.candidate:
        raise ValueError("Los alias del modelo deben ser distintos")
    secret=os.getenv("LLM_API_KEY")
    if not secret:
        raise ValueError("Credencial de inferencia local no configurada")
    from openai import OpenAI
    client=OpenAI(api_key=secret,base_url="http://127.0.0.1:18080/v1",
                  max_retries=0,timeout=60.0)
    cases=approved_cases(args.approved_holdout)
    def inference(model):
        def ask(prompt):
            response=client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":"Respondé brevemente y con precisión. No inventes fuentes."},
                          {"role":"user","content":prompt}],
                temperature=0,max_tokens=220)
            return str(response.choices[0].message.content or "")
        return ask
    baseline=evaluate(cases,inference(args.baseline))
    candidate=evaluate(cases,inference(args.candidate))
    result=gate(baseline,candidate)
    result["model_baseline"]=args.baseline
    result["model_candidate"]=args.candidate
    path=Path(args.output)
    if path.exists():
        raise ValueError("No sobrescribir evaluaciones anteriores")
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({"evaluation_passed":result["evaluation_passed"],
                      "approved_for_promotion":False,
                      "cases":candidate.cases,"result_file":str(path)}))
    return 0 if result["evaluation_passed"] else 2

if __name__=="__main__":
    try:sys.exit(main())
    except (OSError,ValueError) as exc:
        print("Evaluación no realizada:",type(exc).__name__,file=sys.stderr)
        sys.exit(3)
