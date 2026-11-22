"""Exactitud de decisiones: no confundirla con cobertura ni recuperación."""
import importlib.util
import sys
from pathlib import Path
import unittest

src=Path(__file__).resolve().parents[1]/"scripts"/"evaluate_decision_quality.py"
spec=importlib.util.spec_from_file_location("decision_quality",src)
d=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=d
spec.loader.exec_module(d)


def data():
    cases=[]
    for i in range(40):
        actual=i%2==0
        cases.append({
            "case_id":f"q{i:03}","actual":actual,
            "baseline":i%3==0,
            "candidate":actual,
            "baseline_probability":.6 if i%3==0 else .4,
            "candidate_probability":.9 if actual else .1,
        })
    return {"dataset_id":"casos-ficticios-test","label_source":"expertos_independientes","cases":cases}


class QualityTests(unittest.TestCase):
    def test_classification_is_observed_not_invented(self):
        out=d.evaluate(data())
        self.assertEqual(out["cases"],40)
        self.assertEqual(out["candidate"]["accuracy"],1)
        self.assertEqual(out["candidate"]["false_positive_rate"],0)
        self.assertEqual(out["candidate"]["false_negative_rate"],0)
        self.assertEqual(out["candidate"]["brier_score"],.01)
        self.assertTrue(out["non_regression_gate"])

    def test_refuse_no_gold_or_single_class(self):
        obj=data()
        obj["label_source"]="mismo_gpt"
        with self.assertRaisesRegex(ValueError,"independiente"):
            d.evaluate(obj)
        obj=data()
        obj["cases"]=[{"case_id":"x","actual":True,"baseline":True,"candidate":True}]*20
        with self.assertRaisesRegex(ValueError,"ID único"):
            d.evaluate(obj)
        obj=data()
        for c in obj["cases"]:c["actual"]=True
        with self.assertRaisesRegex(ValueError,"positivos y negativos"):
            d.evaluate(obj)


if __name__=="__main__":
    unittest.main()
