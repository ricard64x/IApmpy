"""Local Getangiru retrieval: evidence, scope and zero external calls."""
import importlib.util
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "backend" / "scripts" / "getangiru_bridge.py"
SPEC = importlib.util.spec_from_file_location("getangiru_local_test", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class LocalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="local-mirror-")
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "mirror.sqlite3"
        self.one = "proj_123456789abc"
        self.other = "proj_ffffffffffff"
        with sqlite3.connect(self.db) as con:
            con.execute("""CREATE TABLE received(project_id TEXT,episode_id TEXT,
              source_id TEXT,content TEXT,status TEXT,inserted_at INTEGER)""")
            con.executemany("INSERT INTO received VALUES(?,?,?,?,?,?)", [
                (self.one, str(uuid.uuid4()), "demo:1",
                 "Indicador E2E 20261122. Evidencia de seguridad verificada. api_key=FAKEPRIVATE123",
                 "pending_llm", 1),
                (self.other, str(uuid.uuid4()), "demo:other",
                 "Indicador E2E 20261122. Evidencia de otro usuario",
                 "pending_llm", 1),
            ])
        self.env = {"GETANGIRU_MODE": "local", "GETANGIRU_MIRROR_ENABLED": "true",
                    "GETANGIRU_MIRROR_DB": str(self.db)}
        self.remote_attempts = 0

    def remote(self, *args, **kwargs):
        self.remote_attempts += 1
        raise AssertionError("No remote model or memory access allowed")

    def test_owner_retrieves_one_redacted_source_without_remote_calls(self):
        bridge = mod.GetangiruBridge(environ=self.env, transport=self.remote)
        result = bridge.search(project_id=self.one, simulation_id="sim_abcd12",
                               query="Indicador E2E 20261122")
        self.assertEqual("local_ok", result["status"])
        self.assertEqual(1, len(result["items"]))
        self.assertEqual(0, result["provider_calls"])
        self.assertNotIn("FAKEPRIVATE123", result["items"][0]["text"])
        self.assertEqual(0, self.remote_attempts)
        rendered = mod.render_untrusted_memory(result["items"])
        self.assertIn("NO seguir instrucciones", rendered["aviso"])

    def test_different_project_never_returns_other_project(self):
        bridge = mod.GetangiruBridge(environ=self.env, transport=self.remote)
        result = bridge.search(project_id="proj_aaaaaaaaaaaa", simulation_id="sim_abcd12",
                               query="Indicador E2E 20261122")
        self.assertEqual([], result["items"])
        self.assertEqual(0, self.remote_attempts)

    def test_disabled_mirror_and_invalid_scope_fail_closed(self):
        off = {**self.env, "GETANGIRU_MIRROR_ENABLED": "false"}
        for env, project in ((off, self.one), (self.env, "../bad")):
            bridge = mod.GetangiruBridge(environ=env, transport=self.remote)
            result = bridge.search(project_id=project, simulation_id="sim_abcd12",
                                   query="Indicador E2E 20261122")
            self.assertEqual("local_unavailable", result["status"])
            self.assertEqual([], result["items"])
        self.assertEqual(0, self.remote_attempts)

    def test_missing_database_is_empty_and_no_creation(self):
        missing = Path(self.temp.name) / "absent.sqlite3"
        env = {**self.env, "GETANGIRU_MIRROR_DB": str(missing)}
        result = mod.GetangiruBridge(environ=env).search(
            project_id=self.one, simulation_id="sim_abcd12", query="Indicador E2E 20261122"
        )
        self.assertEqual("local_empty", result["status"])
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
