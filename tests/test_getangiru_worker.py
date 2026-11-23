"""Durable Getangiru sender: no starvation, no network in unit tests."""
import importlib.util
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "integrations" / "getangiru" / "push_to_tenondera.py"


def load_worker():
    spec = importlib.util.spec_from_file_location("getangiru_push_worker_test", FILE)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


class GetangiruSyncWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.worker = load_worker()
        self.worker.SOURCE = Path(self.temp.name) / "source.sqlite3"
        self.worker.STATE = Path(self.temp.name) / "synced.sqlite3"
        with sqlite3.connect(self.worker.SOURCE) as con:
            con.execute("""CREATE TABLE episodes
              (id TEXT, tenant TEXT,space TEXT,content TEXT,source_id TEXT,status TEXT,created_at TEXT)""")

    def add(self, total):
        with sqlite3.connect(self.worker.SOURCE) as con:
            con.executemany("INSERT INTO episodes VALUES(?,?,?,?,?,?,?)", [
                (str(uuid.uuid4()), "tenondera", "proj_123456789abc",
                 "Evidence " + str(i), "demo:" + str(i), "pending_llm",
                 "2026-11-22T23:00:" + str(i%60).zfill(2))
                for i in range(total)
            ])

    def test_112_items_are_drained_without_first_100_starvation(self):
        self.add(112)
        self.worker.send = lambda path, data: (201, {"success": True})
        batches = [self.worker.sync_once(), self.worker.sync_once(), self.worker.sync_once()]
        self.assertEqual([100, 12, 0], [row[1] for row in batches])
        with sqlite3.connect(self.worker.STATE) as con:
            self.assertEqual(112, con.execute("SELECT COUNT(*) FROM synced").fetchone()[0])

    def test_auth_failure_sets_retry_and_stops_further_posts(self):
        self.add(3)
        calls = []
        def failing(path, data):
            calls.append(data["episode_id"])
            return 401, {"success": False}
        self.worker.send = failing
        self.assertEqual(1, self.worker.sync_once()[0])
        self.assertEqual(1, len(calls))
        self.assertEqual(2, self.worker.sync_once()[0])
        self.assertEqual(3, len(calls))  # Already-failed ID is backed off.

    def test_endpoint_rejects_redirectable_or_insecure_destinations(self):
        for url in ("http://example.com", "https://evil.example",
                    "https://iapmpy.fly.dev@evil.example",
                    "https://iapmpy.fly.dev/a", "https://bad.trycloudflare.com.evil.test"):
            self.worker.TARGET = url
            with self.assertRaises(ValueError):
                self.worker.validate_target()
        self.worker.TARGET = "https://iapmpy.fly.dev"
        self.worker.validate_target()


if __name__ == "__main__":
    unittest.main()
