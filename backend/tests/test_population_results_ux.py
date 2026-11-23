"""Contract tests for immutable versioning, participant controls and readable reports."""
import json
import tempfile
import unittest
from pathlib import Path

from app.services.participant_population import (
    population_status, resize_population, MAX_LITE, MAX_OASIS_2GB,
)
from app.services.report_export_html import render_executive_html


def prepared(root: Path, count=3):
    original = [
        {"user_id": i, "username": f"persona_{i}",
         "name": f"Perfil de origen {i}", "bio": "Persona ficticia original",
         "persona": f"Interpretación de prueba {i}"}
        for i in range(count)
    ]
    config = {
        "simulation_id":root.name, "simulation_requirement":"Comparación de costos",
        "agent_configs":[{"agent_id":i,"entity_name":f"Perfil de origen {i}",
                          "entity_type":"Person","entity_uuid":f"uuid_{i}"}
                         for i in range(count)],
        "time_config":{"agents_per_hour_min":1,"agents_per_hour_max":5},
        "event_config":{"initial_posts":[{"poster_agent_id":2,"content":"Prueba"}]},
    }
    root.mkdir(parents=True, exist_ok=True)
    (root/"reddit_profiles.json").write_text(json.dumps(original),encoding="utf-8")
    (root/"simulation_config.json").write_text(json.dumps(config),encoding="utf-8")
    return original,config


class ParticipantPopulationTests(unittest.TestCase):
    def test_expand_and_shrink_without_changing_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"sim_test"
            original,config=prepared(root)
            status=resize_population(root,8,"lightweight")
            self.assertEqual(status["selected_participants"],8)
            self.assertEqual(status["detected_profiles"],3)
            self.assertEqual(status["synthetic_additions"],5)
            people=json.loads((root/"reddit_profiles.json").read_text(encoding="utf-8"))
            self.assertEqual([p["user_id"] for p in people],list(range(8)))
            self.assertTrue(all("sintético" not in p["name"].lower() for p in people[3:]))
            self.assertTrue(all(p["profession"] for p in people[3:]))
            data=json.loads((root/"simulation_config.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data["agent_configs"]),8)
            self.assertEqual(data["simulation_id"],"sim_test")
            self.assertEqual(data["population_metadata"]["synthetic_additions"],5)
            self.assertEqual(len((root/"twitter_profiles.csv").read_text(encoding="utf-8").splitlines()),9)
            self.assertEqual(json.loads((root/"population_base.json").read_text(encoding="utf-8"))["profiles"],original)
            resized=resize_population(root,2,"lightweight")
            self.assertEqual(resized["selected_participants"],2)
            self.assertEqual(resized["detected_profiles"],3)
            self.assertEqual(resized["synthetic_additions"],0)
            self.assertEqual(len(json.loads((root/"reddit_profiles.json").read_text(encoding="utf-8"))),2)
            self.assertEqual(json.loads((root/"population_base.json").read_text(encoding="utf-8"))["config"],config)

    def test_oasis_never_expands_beyond_original_profiles(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"sim_test";prepared(root)
            with self.assertRaisesRegex(ValueError,"2 y 3"):
                resize_population(root,4,"oasis")
            with self.assertRaisesRegex(ValueError,"número entero"):
                resize_population(root,True,"lightweight")
            with self.assertRaisesRegex(ValueError,"2 y 120"):
                resize_population(root,121,"lightweight")

    def test_export_escapes_untrusted_content_and_explains_quality(self):
        metrics={
            "active_participants":1,"total_actions":5,"message_actions":5,
            "cross_agent_messages":0,"recorded_interaction_pairs":0,
            "interaction_quality":{"status":"insufficient","label":"Calidad insuficiente",
                "valid_multiagent_interaction":False,"issues":["No hubo respuestas."]},
            "participants":[{"id":"0","name":"Nombre <script>alert(1)</script>",
                             "actions":5,"messages":5}],
            "by_round":[{"round":"1","count":5}],
            "by_type":[{"type":"CREATE_POST","count":5}],
            "interactions":[],
        }
        rendered=render_executive_html("## Texto\n<script>alert(1)</script>",metrics,"report_test")
        self.assertIn("Calidad insuficiente",rendered)
        self.assertIn("Participantes activos",rendered)
        self.assertIn("Acciones por ronda",rendered)
        self.assertNotIn("<script>alert(1)</script>",rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;",rendered)
        self.assertIn("style-src",rendered)


if __name__=="__main__":
    unittest.main()
