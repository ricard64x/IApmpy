"""Métricas persistentes: solo evidencia real, sin PII ni porcentajes ficticios."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Config
from app.services.efficiency_metrics import get_simulation_efficiency


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")


class EfficiencyMetricTests(unittest.TestCase):
    def test_real_measurements_and_unknown_accuracy_cost(self):
        with tempfile.TemporaryDirectory() as root, patch.object(Config,"UPLOAD_FOLDER",root):
            sim=Path(root)/"simulations"/"sim_metricas01"
            sim.mkdir(parents=True)
            (sim/"state.json").write_text('{"project_id":"proj_demo1111"}')
            (sim/"reddit_profiles.json").write_text(json.dumps([
                {"user_id":1001},{"user_id":1002}
            ]))
            write_jsonl(sim/"llm_usage_metrics.jsonl",[
                {"status":"ok","actual_prompt_tokens":120,"actual_completion_tokens":36,
                 "latency_ms":180,"provider_attempts":1,"retrieved_sources":1},
                {"status":"ok","actual_prompt_tokens":100,"actual_completion_tokens":32,
                 "latency_ms":600,"provider_attempts":2,"retrieved_sources":0},
                {"status":"failed","actual_prompt_tokens":None,"actual_completion_tokens":None,
                 "latency_ms":900,"provider_attempts":3,"retrieved_sources":0},
            ])
            write_jsonl(sim/"getangiru_metrics.jsonl",[
                {"status":"ok","latency_ms":100,"cache_hit":False},
                {"status":"cache","latency_ms":1,"cache_hit":True},
                {"status":"unavailable","latency_ms":2500,"cache_hit":False},
            ])
            write_jsonl(sim/"lightweight_metrics.jsonl",[
                {"round":1,"maxrss_kib":102400,"elapsed_seconds":2.3},
                {"round":2,"maxrss_kib":122880,"elapsed_seconds":5.6},
            ])
            write_jsonl(sim/"reddit"/"actions.jsonl",[
                {"action_type":"CREATE_POST","source_mode":"sintetico_gpt_liviano",
                 "agent_id":1001,"action_args":{"content":"Respuesta sintética 1"}},
                {"action_type":"CREATE_POST","source_mode":"sintetico_gpt_liviano",
                 "agent_id":1002,"action_args":{"content":"Respuesta sintética 1"}},
            ])
            with patch.dict("os.environ",{},clear=False):
                import os
                os.environ.pop("LLM_PRICE_INPUT_PER_1M_USD",None)
                os.environ.pop("LLM_PRICE_OUTPUT_PER_1M_USD",None)
                result=get_simulation_efficiency("sim_metricas01")
            self.assertEqual(result["model"]["calls"],3)
            self.assertEqual(result["model"]["successful_calls"],2)
            self.assertEqual(result["model"]["input_tokens_actual"],220)
            self.assertEqual(result["model"]["output_tokens_actual"],68)
            self.assertEqual(result["model"]["actual_token_calls"],2)
            self.assertEqual(result["model"]["latency_p95_ms"],900)
            self.assertIsNone(result["model"]["cost_usd_actual_from_configured_prices"])
            self.assertEqual(result["memory"]["cache_hits"],1)
            self.assertEqual(result["memory"]["unavailable"],1)
            self.assertEqual(result["quality_structural"]["profile_coverage_percent"],100)
            self.assertEqual(result["quality_structural"]["duplicated_text_percent"],50)
            self.assertIsNone(result["quality_structural"]["factual_accuracy_percent"])
            self.assertEqual(result["resource"]["peak_child_process_rss_mb"],120)
            self.assertIsNone(result["comparability"]["savings_percent"])
            self.assertNotIn("Respuesta sintética",json.dumps(result))

    def test_reject_invalid_id(self):
        with self.assertRaises(ValueError):
            get_simulation_efficiency("../../secreto")


if __name__=="__main__":
    unittest.main()
