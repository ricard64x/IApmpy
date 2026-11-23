"""Tests for factual charts, public-context isolation and candidate gates."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.config import Config
from app.services.simulation_metrics import legacy_metrics,native_metrics
from app.services.model_evaluation import Result,gate,approved_cases
from app.utils.public_context import context_for_local_qwen,public_topic

class MetricsAndLearningTests(unittest.TestCase):
    def test_legacy_rounds_people_dates_and_interactions(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)/"twitter";base.mkdir()
            rows=[
                {"agent_id":1,"agent_name":"Agente A","round":1,"timestamp":"2026-11-23T10:01:00Z","platform":"twitter",
                 "action_type":"CREATE_POST","action_args":{"content":"Mensaje sintético"}},
                {"agent_id":2,"agent_name":"Agente B","round":2,"timestamp":"2026-11-23T11:01:00Z","platform":"twitter",
                 "action_type":"CREATE_COMMENT","action_args":{"content":"Respuesta simulada","target_agent_id":1}},
            ]
            (base/"actions.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            result=legacy_metrics("sim_123",root)
            self.assertEqual(result["active_participants"],2)
            self.assertEqual(result["message_actions"],2)
            self.assertEqual(result["recorded_interaction_pairs"],1)
            self.assertEqual(result["by_day"][0]["count"],2)
            self.assertEqual(len(result["by_round"]),2)
            self.assertEqual(result["date_basis"],"timestamp de ejecución; no es fecha del escenario simulado")

    def test_native_decisions_are_not_false_conversations(self):
        rows=[{"actor_uuid":"actor_a","actor_type":"SecurityTeam","phase":1,
               "action_text":"Revisar evidencia","created_at":"2026-11-23T14:00:00+00:00"}]
        m=native_metrics(rows)
        self.assertEqual(m["total_actions"],1)
        self.assertEqual(m["message_actions"],0)
        self.assertEqual(m["active_participants"],1)

    def test_public_context_requires_enable_and_never_sends_private_prompt(self):
        previous=Config.UPLOAD_FOLDER
        old=os.environ.get("GETANGIRU_PUBLIC_CONTEXT_ENABLED")
        with tempfile.TemporaryDirectory() as td:
            try:
                Config.UPLOAD_FOLDER=td
                os.environ["GETANGIRU_PUBLIC_CONTEXT_ENABLED"]="true"
                p=Path(td)/"getangiru"/"public-context.sqlite3";p.parent.mkdir()
                with sqlite3.connect(p) as c:
                    c.execute("""CREATE TABLE public_sources(
                       id TEXT,source TEXT,url TEXT,title TEXT,summary TEXT,published TEXT,
                       topic TEXT,received_at INTEGER)""")
                    c.execute("INSERT INTO public_sources VALUES(?,?,?,?,?,?,?,?)",
                     ("abc","cisa","https://www.cisa.gov/test","Alerta de vulnerabilidad",
                      "Análisis publicado", "2026-11-23", "vulnerabilidad",1))
                msg=[{"role":"user","content":"Revisar vulnerabilidad CVE-XXXX en expediente PRIVADO"}]
                result=context_for_local_qwen(msg)
                self.assertIn("https://www.cisa.gov/test",result)
                self.assertNotIn("PRIVADO",result)
                self.assertIsNone(context_for_local_qwen([{"role":"user","content":"Hola"}]))
            finally:
                Config.UPLOAD_FOLDER=previous
                if old is None:os.environ.pop("GETANGIRU_PUBLIC_CONTEXT_ENABLED",None)
                else:os.environ["GETANGIRU_PUBLIC_CONTEXT_ENABLED"]=old

    def test_training_gate_only_recommends_and_never_promotes(self):
        baseline=Result(.70,.99,100,40)
        candidate=Result(.80,1.0,110,40)
        check=gate(baseline,candidate)
        self.assertTrue(check["evaluation_passed"])
        self.assertFalse(check["approved_for_promotion"])
        self.assertTrue(check["human_release_approval_required"])
        self.assertFalse(gate(baseline,Result(.65,.95,90,40))["evaluation_passed"])

if __name__=="__main__":
    unittest.main()
