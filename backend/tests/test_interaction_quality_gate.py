"""Regression: do not certify a one-voice synthetic conversation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.simulation_metrics import summarize, legacy_metrics
from app.services.simulation_execution import validate_execution_settings
from scripts.run_lightweight_simulation import execute


class InteractionQualityGateTests(unittest.TestCase):
    def test_report_flags_historical_single_voice_without_rewriting(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "twitter"
            path.mkdir()
            rows = [
                {"agent_id": 1, "action_type": "CREATE_POST",
                 "action_args": {"content": "Mensaje sintético"}} for _ in range(7)
            ]
            original = "\n".join(json.dumps(r) for r in rows)
            file = path / "actions.jsonl"
            file.write_text(original, encoding="utf-8")
            m = legacy_metrics("sim_historico", td)
            self.assertEqual(m["active_participants"], 1)
            self.assertEqual(m["recorded_interaction_pairs"], 0)
            self.assertEqual(m["interaction_quality"]["status"], "insufficient")
            self.assertFalse(m["interaction_quality"]["valid_multiagent_interaction"])
            self.assertEqual(file.read_text(encoding="utf-8"), original)

    def test_replies_must_target_an_actual_different_agent(self):
        rows = [
            {"agent_id": 1, "action_type": "CREATE_POST"},
            {"agent_id": 1, "action_type": "CREATE_COMMENT", "action_args": {"target_agent_id": 999}},
            {"agent_id": 2, "action_type": "CREATE_COMMENT", "action_args": {"target_agent_id": 1}},
            {"agent_id": 1, "action_type": "CREATE_COMMENT", "action_args": {"target_agent_id": 2}},
        ]
        m = summarize(rows, source="reddit")
        self.assertEqual(m["recorded_interaction_pairs"], 2)
        self.assertEqual(m["cross_agent_messages"], 2)
        self.assertEqual(m["interaction_quality"]["status"], "acceptable")
        self.assertEqual(m["interactions"][0]["count"], 1)

    def test_cross_platform_reference_is_not_an_interaction(self):
        rows = [
            {"agent_id": 1, "platform": "twitter", "action_type": "CREATE_POST"},
            {"agent_id": 2, "platform": "reddit", "action_type": "CREATE_COMMENT",
             "action_args": {"target_agent_id": 1}},
            {"agent_id": 2, "platform": "reddit", "action_type": "CREATE_COMMENT",
             "action_args": {"target_agent_id": 1}},
        ]
        m = summarize(rows, source="oasis")
        self.assertEqual(m["recorded_interaction_pairs"], 0)
        self.assertEqual(m["cross_agent_messages"], 0)
        self.assertEqual(m["interaction_quality"]["status"], "insufficient")

    def test_dialogue_preflight_rejects_one_round(self):
        with self.assertRaisesRegex(ValueError, "2 rondas"):
            validate_execution_settings({
                "platform": "reddit", "auto_finalize": True,
                "max_rounds": 1, "engine_mode": "lightweight",
                "interaction_mode": "dialogue"})

    def _prepared(self, root, n):
        (root / "reddit_profiles.json").write_text(
            json.dumps([{"user_id": i, "name": f"Perfil {i}",
                         "persona": "Personaje de prueba"} for i in range(1, n+1)]),
            encoding="utf-8")
        (root / "simulation_config.json").write_text(json.dumps({
            "simulation_requirement": "Hipótesis ficticia de comparación de costos",
            "time_config": {"minutes_per_round": 30, "total_simulation_hours": 2}
        }), encoding="utf-8")
        (root / "execution_settings.json").write_text(
            '{"interaction_mode":"dialogue"}', encoding="utf-8")
        return root / "simulation_config.json"

    def _model(self, system, prompt):
        data = json.loads(prompt)
        return {"actions": [
            {"agent_id": p["id"],
             "content": "Respuesta sintética razonada sobre los costos y proveedores "
                        "del escenario ficticio para evaluar la decisión."}
            for p in data["participantes"]]}

    def test_rejects_single_prepared_profile_before_creating_actions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = self._prepared(root, 1)
            with self.assertRaisesRegex(ValueError, "2 participantes"):
                execute(cfg, "reddit", 3, request_fn=self._model)
            self.assertFalse((root / "reddit" / "actions.jsonl").exists())

    def test_two_profiles_parallel_repair_creates_two_real_directed_replies(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = self._prepared(root, 2)
            with patch("scripts.run_lightweight_simulation.GetangiruBridge") as bridge:
                bridge.return_value.mode = "off"
                bridge.return_value.search.return_value = {"items": [], "status": "off"}
                result = execute(cfg, "parallel", 2, request_fn=self._model)
            self.assertEqual(result["profiles"], 2)
            self.assertEqual(result["replies"], 2)
            self.assertEqual(result["actions"], 3)  # one bounded additional reply
            self.assertEqual(result["model_batches"], 3)
            m = legacy_metrics("sim_dos", root)
            self.assertTrue(m["interaction_quality"]["valid_multiagent_interaction"])
            self.assertEqual(m["cross_agent_messages"], 2)
            self.assertEqual({p["id"] for p in m["participants"]}, {"1", "2"})
            self.assertEqual(m["recorded_interaction_pairs"], 2)


if __name__ == "__main__":
    unittest.main()
