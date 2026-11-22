"""Regression tests for cached Spanish restoration of historical reports."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services import report_localization as mod
from app.services.report_agent import ReportStatus


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.report_id = "report_legacy12"
        (Path(self.temp.name) / self.report_id).mkdir()
        self.outline = {
            "title": "模拟报告", "summary": "重要结论",
            "sections": [{"title": "第一章", "content": ""}],
        }
        self.report = SimpleNamespace(
            report_id=self.report_id,
            status=ReportStatus.COMPLETED,
            outline=SimpleNamespace(to_dict=lambda: self.outline),
        )
        self.llm = SimpleNamespace(
            chat_json=lambda **kwargs: {
                "title": "Informe simulado", "summary": "Conclusiones principales",
                "section_titles": ["Primera sección"],
            },
            chat=lambda **kwargs: "El escenario plantea opiniones hipotéticas.",
        )
        self.patches = [
            patch.object(mod.ReportManager, "REPORTS_DIR", self.temp.name),
            patch.object(mod.ReportManager, "get_report", return_value=self.report),
            patch.object(mod.ReportManager, "get_generated_sections", return_value=[
                {"section_index": 1, "content": "模拟分析来自虚拟参与者。"},
            ]),
            patch.object(mod, "LLMClient", return_value=self.llm),
        ]
        for patcher in self.patches: patcher.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def test_translate_once_then_cached_no_additional_model_calls(self):
        a = mod.translate_saved_part(self.report_id, "outline")
        b = mod.translate_saved_part(self.report_id, "section_1")
        self.assertEqual(a["outline"]["title"], "Informe simulado")
        self.assertEqual(b["content"], "El escenario plantea opiniones hipotéticas.")
        self.assertEqual(mod.translate_saved_part(self.report_id, "outline")["from_cache"], True)
        self.assertEqual(mod.translate_saved_part(self.report_id, "section_1")["from_cache"], True)
        saved = mod.localized_markdown(self.report_id)
        self.assertIn("Informe simulado", saved)
        self.assertIn("Primera sección", saved)
        self.assertIn("El escenario plantea opiniones", saved)

    def test_invalid_part_rejected(self):
        for part in ("../meta", "section_0", "section_99", "unknown"):
            with self.subTest(part=part), self.assertRaises(ValueError):
                mod.translate_saved_part(self.report_id, part)

    def test_original_unchanged(self):
        mod.translate_saved_part(self.report_id, "outline")
        mod.translate_saved_part(self.report_id, "section_1")
        self.assertEqual(self.outline["title"], "模拟报告")
        self.assertIsNotNone(mod.get_saved_translation(self.report_id, "outline"))


if __name__ == "__main__":
    unittest.main()
