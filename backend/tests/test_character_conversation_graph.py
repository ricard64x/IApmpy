"""Evidence-backed social conversation graphs; no invented real network activity."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.character_interaction_graph import character_alias, character_graph
from app.services.simulation_execution import validate_execution_settings
from app.services.report_export_html import render_executive_html
from scripts.run_lightweight_simulation import execute


class ConversationGraphTests(unittest.TestCase):
    def test_names_professions_rooms_and_credible_edges(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            profiles=[
                {"user_id":0,"name":"Personaje A","profession":"Arquitecta"},
                {"user_id":1,"name":"Personaje B","profession":"Analista financiero"},
                {"user_id":2,"name":"Personaje C","profession":"Docente"},
            ]
            (root/"reddit_profiles.json").write_text(json.dumps(profiles),encoding="utf-8")
            (root/"reddit").mkdir()
            rows=[
                {"agent_id":0,"agent_name":"Personaje A","social_space":"foro",
                 "action_type":"CREATE_POST","action_args":{"content":"¿Qué opinan de este diseño?","synthetic_action_id":"a0"}},
                {"agent_id":1,"agent_name":"Personaje B","social_space":"foro",
                 "action_type":"CREATE_COMMENT",
                 "action_args":{"target_agent_id":0,"reply_to_action_id":"a0","content":"El presupuesto es importante."}},
                {"agent_id":2,"agent_name":"Personaje C","social_space":"profesional",
                 "action_type":"CREATE_COMMENT",
                 "action_args":{"target_agent_id":0,"content":"No puede contar como respuesta entre espacios."}},
                {"agent_id":0,"agent_name":"Personaje A","social_space":"foro",
                 "action_type":"CREATE_COMMENT",
                 "action_args":{"target_agent_id":1,"content":"Entonces contrastemos alternativas."}},
            ]
            (root/"reddit"/"actions.jsonl").write_text(
                "\n".join(json.dumps(x) for x in rows),encoding="utf-8")
            graph=character_graph("sim_prueba",root)
            self.assertEqual(graph["directed_responses"],2)
            self.assertEqual(len(graph["edges"]),2)
            self.assertEqual(graph["nodes"][0]["name"],character_alias(0))
            self.assertEqual(graph["nodes"][0]["profession"],"Arquitecta")
            self.assertEqual(set(graph["rooms"]),{"foro","profesional"})
            self.assertEqual(graph["messages"][1]["recipient"],character_alias(0))
            self.assertIsNone(graph["messages"][2]["recipient"])
            self.assertTrue(graph["simulated_only"])

    def test_export_safely_prints_saved_conversations(self):
        metrics={"active_participants":2,"message_actions":2,"total_actions":2,
          "recorded_interaction_pairs":1,"cross_agent_messages":1,
          "interaction_quality":{"valid_multiagent_interaction":False,"label":"Insuficiente"},
          "participants":[{"id":"0","name":"Realidad","actions":1,"messages":1}],
          "by_round":[],"by_type":[],"interactions":[],
          "by_social_space":[{"space":"profesional","count":2}],
          "conversation_archive":{"nodes":[{"id":"0","name":"Valeria Benítez","profession":"Arquitecta"}],
           "total_actions":2,"messages":[{"author":"Valeria Benítez","profession":"Arquitecta",
             "recipient":"Mateo Cabrera","channel":"profesional",
             "round":1,"content":"<script>alert(1)</script>"}]}}
        html=render_executive_html("## Hallazgos",metrics,"report_test")
        self.assertIn("Dónde se desarrollaron las conversaciones",html)
        self.assertIn("Comunidad profesional",html)
        self.assertIn("Valeria Benítez",html)
        self.assertIn("Arquitecta",html)
        self.assertNotIn("<script>alert(1)</script>",html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;",html)

    def test_social_settings_are_validated_and_bounded(self):
        base={"platform":"parallel","engine_mode":"lightweight","auto_finalize":True,
              "interaction_mode":"dialogue","max_rounds":4,
              "social_spaces":["plaza","profesional"],"dialogue_depth":3}
        result=validate_execution_settings(base)
        self.assertEqual(result["dialogue_depth"],3)
        self.assertEqual(result["social_spaces"],["plaza","profesional"])
        for alteration in ({"dialogue_depth":4},{"social_spaces":["videos","videos"]},
                           {"social_spaces":["inexistente"]}):
            with self.subTest(alteration=alteration),self.assertRaises(ValueError):
                validate_execution_settings({**base,**alteration})
        with self.assertRaises(ValueError):
            validate_execution_settings({**base,"engine_mode":"oasis"})

    def test_two_rooms_have_real_dialogues_and_log_origin(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            profiles=[{"user_id":i,"name":f"Personaje {i}","profession":"Profesional",
                       "persona":"Analiza costos y calidad"} for i in range(8)]
            (root/"reddit_profiles.json").write_text(json.dumps(profiles),encoding="utf-8")
            cfg=root/"simulation_config.json"
            cfg.write_text(json.dumps({"simulation_requirement":"Decidir inversión",
                "time_config":{"minutes_per_round":30,"total_simulation_hours":2}}),encoding="utf-8")
            (root/"execution_settings.json").write_text(json.dumps({
                "interaction_mode":"dialogue","social_spaces":["plaza","foro"],
                "dialogue_depth":2}),encoding="utf-8")
            def model(system,prompt):
                data=json.loads(prompt)
                return {"actions":[{"agent_id":item["id"],
                         "content":"Tengo dudas sobre costos, garantías y beneficios; revisemos la propuesta."
                        } for item in data["participantes"]]}
            with patch("scripts.run_lightweight_simulation.GetangiruBridge") as bridge:
                bridge.return_value.mode="off"
                bridge.return_value.search.return_value={"items":[],"status":"off"}
                result=execute(cfg,"parallel",2,request_fn=model)
            self.assertGreater(result["replies"],2)
            self.assertLessEqual(result["model_batches"],40)
            graph=character_graph("sim_prueba",root)
            self.assertEqual(set(graph["rooms"]),{"plaza","foro"})
            self.assertTrue(all(e["channel"] in ("plaza","foro") for e in graph["edges"]))
            self.assertGreater(graph["directed_responses"],2)


if __name__=="__main__":
    unittest.main()
