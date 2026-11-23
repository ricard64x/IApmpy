"""Native simulation smoke/regression: isolation, real progress and no cloud calls."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.services.getangiru_native_simulation import NativeSimStore, ROLES


class FakeQwen:
    def __init__(self, answer=None):
        self.calls=0
        self.answer=answer or '{"focus":"identidad","hypothesis":"Investigar accesos privilegiados."}'
    def chat(self, **kwargs):
        self.calls+=1
        return self.answer


def graph():
    names=list(ROLES)
    return {
        "graph_id":"gtg_aaaaaaaaaaaaaaaaaaaaaaaa",
        "nodes":[{
            "uuid":"n"+str(i), "name":name,
            "labels":[name],
            "attributes":{"source_id":"doc:test","evidence":"El documento contiene "+name}
        } for i,name in enumerate(names)],
        "edge_count":9,
    }


class LocalSimulationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s=NativeSimStore(self.tmp.name+"/native.sqlite")
        self.graph=graph()

    def create(self,mode="rules"):
        return self.s.create(project_id="proj_0123456789ab",
                             graph_id=self.graph["graph_id"], mode=mode,
                             source_hash="sample")

    def test_private_simulation_store_permissions(self):
        import stat
        self.assertEqual(0o600, stat.S_IMODE(self.s.path.stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE(self.s.path.parent.stat().st_mode))

    def test_full_four_phase_workflow_is_durable_and_auditable(self):
        row=self.create()
        self.s.execute(row["id"],self.graph,"Simulación ficticia de accesos")
        fresh=NativeSimStore(self.s.path).public(row["id"])
        self.assertEqual("completed",fresh["status"])
        self.assertEqual(4,fresh["phase"])
        self.assertEqual(32,len(fresh["actions"]))
        self.assertEqual(100,fresh["report"]["evidence_coverage_pct"])
        self.assertEqual(0,fresh["report"]["external_model_requests"])
        self.assertEqual(0,fresh["report"]["inferred_causal_facts"])
        self.assertTrue(all(a["origin"]=="reglas_simuladas" for a in fresh["actions"]))
        self.assertTrue(all(a["evidence_source"]=="doc:test" for a in fresh["actions"]))

    def test_hybrid_uses_one_local_request_and_fallback_is_labelled(self):
        model=FakeQwen()
        x=self.create(mode="hybrid")
        self.s.execute(x["id"],self.graph,"Test",llm=model)
        report=self.s.public(x["id"])["report"]
        self.assertEqual(1,model.calls)
        self.assertEqual(1,report["local_llm_requests"])
        self.assertEqual("qwen_local",report["plan"]["basis"])
        invalid=FakeQwen("no es JSON")
        y=self.create(mode="hybrid")
        self.s.execute(y["id"],self.graph,"Test",llm=invalid)
        report=self.s.public(y["id"])["report"]
        self.assertEqual(1,report["local_llm_requests"])
        self.assertEqual("reglas_fallback",report["plan"]["basis"])
        self.assertTrue(report["local_model_fallback"])

    def test_active_run_blocks_new_run(self):
        row=self.create()
        with self.assertRaisesRegex(RuntimeError,"otra simulación"):
            self.create()
        self.s.execute(row["id"],self.graph,"Test")
        self.assertNotEqual(row["id"],self.create()["id"])

    def test_feedback_is_human_only_reviewed_and_informs_next_run(self):
        first=self.create()
        self.s.execute(first["id"],self.graph,"Test")
        actor=self.graph["nodes"][0]
        self.s.feedback(first["id"],actor_uuid=actor["uuid"],phase=1,
                        verdict="reject",note="Exigir evidencia de validación")
        self.assertEqual({"reject":1},self.s.quality(first["id"]))
        snapshot=self.s.public(first["id"])
        self.assertEqual(1,snapshot["human_validation"]["reviewed"])
        self.assertEqual(0.0,snapshot["human_validation"]["acceptance_rate_pct"])
        second=self.create()
        self.s.execute(second["id"],self.graph,"Test")
        plan=self.s.public(second["id"])["report"]["plan"]
        self.assertEqual("ampliar evidencia",plan["review_priority"])
        self.assertEqual({"reject":1},plan["past_human_feedback"])
        second_actions=self.s.public(second["id"])["actions"]
        followup=[a for a in second_actions if a["actor_uuid"]==actor["uuid"]
                  and a["phase"]==4]
        self.assertEqual(1,len(followup))
        self.assertIn("validación reforzada",followup[0]["action_text"])
        with self.assertRaises(ValueError):
            self.s.feedback(second["id"],actor_uuid=actor["uuid"],phase=2,
                            verdict="invented",note="x")
        for note,phase in ((None,2),("text",True),(123,2)):
            with self.subTest(note=note,phase=phase),self.assertRaises(ValueError):
                self.s.feedback(second["id"],actor_uuid=actor["uuid"],phase=phase,
                                verdict="accept",note=note)

    def test_missing_evidence_fails_closed(self):
        row=self.create()
        data=graph()
        data["nodes"][0]["attributes"]["source_id"]=""
        with self.assertRaises(ValueError):
            self.s.execute(row["id"],data,"Test")
        self.assertIn(self.s.get(row["id"])["state"],("queued","failed"))

    def test_stale_run_can_be_recovered_without_replay(self):
        first=self.create()
        old=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
        with sqlite3.connect(self.s.path) as con:
            con.execute("UPDATE runs SET updated_at=? WHERE id=?",(old,first["id"]))
        second=self.create()
        self.assertEqual("interrupted",self.s.get(first["id"])["state"])
        self.assertEqual("queued",second["state"])

    def test_agent_limit(self):
        row=self.create()
        bad=graph()
        bad["nodes"]*=2
        with self.assertRaises(ValueError):
            self.s.execute(row["id"],bad,"Test")


if __name__=="__main__":
    unittest.main()
