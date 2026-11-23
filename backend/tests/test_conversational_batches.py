"""Contract tests: synthetic agent replies must be causally grounded and bounded."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.run_lightweight_simulation import execute
from test_character_conversation_graph import ConversationGraphTests  # regression suite included in CI discover

class ConversationalBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        profiles=[{"user_id":i,"name":f"Agente {i}","persona":"Perfil ficticio"} for i in range(1,7)]
        (self.root/"reddit_profiles.json").write_text(json.dumps(profiles),encoding="utf-8")
        self.cfg=self.root/"simulation_config.json"
        self.cfg.write_text(json.dumps({"simulation_requirement":"Escenario ficticio de decisiones",
                                       "time_config":{"minutes_per_round":30,"total_simulation_hours":3}}),encoding="utf-8")
        self.observed=[]

    def tearDown(self):
        self.temp.cleanup()

    def model(self,system,prompt):
        data=json.loads(prompt)
        self.observed.append(data)
        return {"actions":[{"agent_id":p["id"],
                            "content":"Respuesta ficticia de perfil a situación de prueba y evolución del escenario."}
                           for p in data["participantes"]]}

    def events(self,name):
        return [json.loads(line) for line in (self.root/name/"actions.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_dialogue_one_llm_call_per_batch_and_provenance(self):
        (self.root/"execution_settings.json").write_text('{"interaction_mode":"dialogue"}')
        with patch("scripts.run_lightweight_simulation.GetangiruBridge") as bridge:
            bridge.return_value.mode="off"
            bridge.return_value.search.return_value={"items":[],"status":"off"}
            result=execute(self.cfg,"reddit",3,request_fn=self.model)
        rows=self.events("reddit")
        posts=[r for r in rows if r.get("action_type")=="CREATE_POST"]
        replies=[r for r in rows if r.get("action_type")=="CREATE_COMMENT"]
        self.assertEqual(result["actions"],12)
        self.assertEqual(result["replies"],10)
        self.assertEqual(result["model_batches"],5)
        self.assertEqual(len(posts),2)
        self.assertEqual(len(replies),10)
        self.assertFalse("conversacion_sintetica_previa_no_confiable" in self.observed[0])
        self.assertTrue("conversacion_sintetica_previa_no_confiable" in self.observed[1])
        for row in replies:
            args=row["action_args"]
            self.assertIn(args["target_agent_id"],[1,2,3,4,5,6])
            self.assertNotEqual(args["target_agent_id"],row["agent_id"])
            self.assertTrue(args["reply_to_action_id"].startswith("reddit:r"))
            self.assertTrue(args["root_post_id"].startswith("reddit:r"))
        for row in rows:
            if row.get("event_type")=="round_end":
                self.assertGreaterEqual(row["round"],1)
        self.assertEqual(len([r for r in rows if r.get("event_type")=="round_end"]),3)

    def test_legacy_posts_remain_independent(self):
        with patch("scripts.run_lightweight_simulation.GetangiruBridge") as bridge:
            bridge.return_value.mode="off"
            bridge.return_value.search.return_value={"items":[],"status":"off"}
            result=execute(self.cfg,"parallel",3,request_fn=self.model)
        self.assertEqual(result["replies"],0)
        events=self.events("twitter")+self.events("reddit")
        actions=[r for r in events if "action_type" in r]
        self.assertEqual(len(actions),6)
        self.assertEqual({r["action_type"] for r in actions},{"CREATE_POST"})

    def test_parallel_dialogue_never_crosses_platforms(self):
        (self.root/"execution_settings.json").write_text('{"interaction_mode":"dialogue"}')
        with patch("scripts.run_lightweight_simulation.GetangiruBridge") as bridge:
            bridge.return_value.mode="off"
            bridge.return_value.search.return_value={"items":[],"status":"off"}
            result=execute(self.cfg,"parallel",3,request_fn=self.model)
        self.assertEqual(result["actions"],12)
        self.assertEqual(result["replies"],8)
        for platform in ("twitter","reddit"):
            entries=self.events(platform)
            for row in entries:
                if row.get("action_type")=="CREATE_COMMENT":
                    self.assertTrue(row["action_args"]["reply_to_action_id"].startswith(platform+":"))
            self.assertEqual(len([r for r in entries if r.get("event_type")=="round_end"]),3)

if __name__=="__main__":
    unittest.main()
