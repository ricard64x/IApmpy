"""Las cifras A/B se producen solo con etiquetas independientes y casos pareados."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_getangiru.py"
SPEC = importlib.util.spec_from_file_location("benchmark_getangiru", SCRIPT)
bench = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bench
SPEC.loader.exec_module(bench)


def dataset(better=True):
    cases=[]
    for i in range(15):
        gold=f"doc:{i}"
        cases.append({
            "case_id":f"case{i+1:02}", "gold":[gold],
            "baseline":[f"wrong:{i}",gold],
            "candidate":[gold] if better else [f"wrong:{i}"],
            "baseline_latency_ms":100,
            "candidate_latency_ms":50,
            "baseline_tokens":400,
            "candidate_tokens":300,
        })
    return {"dataset_id":"mock-labels-only","label_source":"expertos_independientes",
            "cases":cases}


class BenchmarkTests(unittest.TestCase):
    def test_metrics_labelled_and_paired(self):
        result=bench.compare(dataset())
        self.assertEqual(result["sample_count"],15)
        self.assertEqual(result["candidate"]["recall_at_k"],1)
        self.assertEqual(result["baseline"]["precision_at_k"],.5)
        self.assertEqual(result["candidate"]["precision_at_k"],1)
        self.assertEqual(result["delta"]["token_reduction_percent"],25)
        self.assertEqual(result["candidate"]["latency_p95_ms"],50)
        self.assertTrue(result["retrieval_non_regression_gate"])
        self.assertIn("no exactitud de predicciones",result["disclaimer"])

    def test_regression_fails_predeclared_gate(self):
        result=bench.compare(dataset(better=False))
        self.assertFalse(result["retrieval_non_regression_gate"])

    def test_requires_independent_labels_and_sample_size(self):
        obj=dataset()
        obj["cases"]=obj["cases"][:2]
        with self.assertRaisesRegex(ValueError,"12 casos"):
            bench.compare(obj)
        obj=dataset()
        obj["label_source"]="generated_by_same_model"
        with self.assertRaisesRegex(ValueError,"independiente"):
            bench.compare(obj)
        obj=dataset()
        obj["cases"][0]["gold"]=[]
        with self.assertRaisesRegex(ValueError,"fuentes de referencia"):
            bench.compare(obj)


if __name__=="__main__":
    unittest.main()
