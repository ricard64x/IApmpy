"""No-network regression tests for post-report chats, surveys and durable history."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app.services import report_interactions as interactions
from app.services.report_agent import ReportStatus

REPORT_ID = "report_test123"
SIM_ID = "sim_test123"


class ReportInteractionsTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        (Path(self.root.name) / REPORT_ID).mkdir()
        self.report = SimpleNamespace(
            report_id=REPORT_ID, simulation_id=SIM_ID,
            status=ReportStatus.COMPLETED,
            simulation_requirement="Situación hipotética de banca digital",
            markdown_content="# Escenario\nLas respuestas son sintéticas.",
        )
        self.fake_llm = SimpleNamespace(
            chat=lambda **kwargs: "Una opinión sintética; no es evidencia real.",
            chat_json=lambda **kwargs: {"answers": [
                {"agent_id": 0, "response": "Apoyo la idea."},
                {"agent_id": 1, "response": "Tengo dudas de seguridad."},
            ]},
        )
        self.patches = [
            patch.object(interactions.ReportManager, "REPORTS_DIR", self.root.name),
            patch.object(interactions.ReportManager, "get_report", return_value=self.report),
            patch.object(interactions, "LLMClient", return_value=self.fake_llm),
            patch.object(interactions.SimulationManager, "get_simulation",
                         return_value=SimpleNamespace(
                             enable_twitter=True, enable_reddit=True,
                             get_default_platform=lambda: "reddit",
                         )),
            patch.object(interactions.SimulationManager, "get_profiles",
                         return_value=[
                             {"username":"Participante A","bio":"Estudiante"},
                             {"username":"Participante B","bio":"Comerciante"},
                         ]),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.root.cleanup()

    def test_report_chat_persists_and_can_be_reloaded(self):
        record = interactions.interact(REPORT_ID, SIM_ID, "chat", "¿Qué opinión aparece?")
        self.assertEqual(record["source_mode"], "sintetico_posterior")
        self.assertIn("sintética", record["response"])
        loaded = interactions.history_for_report(REPORT_ID, SIM_ID)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["question"], "¿Qué opinión aparece?")

    def test_participant_chat_uses_saved_profile_not_oasis(self):
        with patch("app.services.simulation_runner.SimulationRunner.start_simulation",
                   side_effect=AssertionError("Must never start OASIS")):
            result = interactions.interact(
                REPORT_ID, SIM_ID, "chat", "¿Qué opinás?",
                target="participant", agent_id=1,
            )
        self.assertEqual(result["target"], "participant")
        self.assertEqual(result["agent_id"], 1)

    def test_survey_uses_one_llm_request_for_two_profiles(self):
        call_count = [0]
        def fake_chat_json(**kwargs):
            call_count[0] += 1
            return self.fake_llm.chat_json_original(**kwargs)
        self.fake_llm.chat_json_original = self.fake_llm.chat_json
        self.fake_llm.chat_json = fake_chat_json
        record = interactions.interact(REPORT_ID, SIM_ID, "survey", "¿Confiarías?", agent_ids=[0,1])
        self.assertEqual(call_count[0], 1)
        self.assertEqual(len(record["results"]), 2)
        self.assertEqual(record["results"][1]["answer"], "Tengo dudas de seguridad.")

    def test_out_of_scope_and_oversized_rejected_without_model_call(self):
        with self.assertRaises(ValueError):
            interactions.interact(REPORT_ID, "sim_other", "chat", "Una pregunta")
        for ids in ([0,0], list(range(9)), []):
            with self.assertRaises(ValueError):
                interactions.interact(REPORT_ID, SIM_ID, "survey", "Una pregunta", agent_ids=ids)
        with self.assertRaises(ValueError):
            interactions.interact(REPORT_ID, SIM_ID, "chat", "X" * 2000)

    def test_only_completed_reports_are_queryable(self):
        self.report.status = ReportStatus.GENERATING
        with self.assertRaises(ValueError):
            interactions.history_for_report(REPORT_ID, SIM_ID)


if __name__ == "__main__":
    unittest.main()
