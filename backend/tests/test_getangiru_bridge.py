"""Getangiru inbound bridge: security, isolation, idempotency and local lookup."""
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from app.config import Config
from app.api.getangiru_bridge import getangiru_bp


class TestGetangiruBridge(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="getangiru-ci-")
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(os.environ, {
            "GETANGIRU_MIRROR_ENABLED": "true",
            "GETANGIRU_PUSH_SECRET": "only-for-unit-tests-" + "x" * 52,
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.override = patch.object(Config, "UPLOAD_FOLDER", self.folder.name)
        self.override.start()
        self.addCleanup(self.override.stop)
        self.project = "proj_0123456789ab"
        project_file = Path(self.folder.name) / "projects" / self.project / "project.json"
        project_file.parent.mkdir(parents=True)
        project_file.write_text("{}", encoding="utf-8")
        app = Flask("getangiru-test")
        app.config["TESTING"] = True
        app.register_blueprint(getangiru_bp)
        self.client = app.test_client()
        self.secret = os.environ["GETANGIRU_PUSH_SECRET"].encode()
        self.episode = str(uuid.uuid4())

    def signed(self, path, obj, *, stamp=None, nonce=None, change_signature=False):
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
        stamp = str(int(time.time())) if stamp is None else str(stamp)
        nonce = uuid.uuid4().hex if nonce is None else nonce
        signature = hmac.new(
            self.secret, stamp.encode() + b"." + nonce.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if change_signature:
            signature = "0" * 64 if signature != "0" * 64 else "1" * 64
        return self.client.post(
            path, data=body, content_type="application/json",
            headers={
                "X-Getangiru-Timestamp": stamp,
                "X-Getangiru-Nonce": nonce,
                "X-Getangiru-Signature": signature,
            },
        )

    def payload(self):
        return {
            "project_id": self.project, "space": self.project,
            "episode_id": self.episode, "source_id": "demo-001",
            "content": "Getangiru recuerda la evidencia del escenario de prueba.",
            "status": "pending_llm",
        }

    def test_signed_ping_and_replay(self):
        nonce = uuid.uuid4().hex
        body = {"test": "synthetic"}
        self.assertEqual(200, self.signed("/__getangiru/ping", body, nonce=nonce).status_code)
        self.assertEqual(409, self.signed("/__getangiru/ping", body, nonce=nonce).status_code)

    def test_bad_auth_and_expired(self):
        self.assertEqual(401, self.client.post("/__getangiru/ping", json={}).status_code)
        self.assertEqual(401, self.signed("/__getangiru/ping", {}, change_signature=True).status_code)
        self.assertEqual(401, self.signed("/__getangiru/ping", {}, stamp=int(time.time())-600).status_code)

    def test_ingest_idempotency_and_access_control(self):
        one = self.signed("/__getangiru/ingest", self.payload())
        self.assertEqual(201, one.status_code, one.get_data(as_text=True))
        two = self.signed("/__getangiru/ingest", self.payload())
        self.assertEqual(200, two.status_code)
        self.assertTrue(two.json["duplicate"])
        changed = self.payload()
        changed["content"] += " Manipulación"
        self.assertEqual(409, self.signed("/__getangiru/ingest", changed).status_code)
        with patch("app.auth.can_access_project", return_value=True):
            got = self.client.get(f"/api/getangiru/project/{self.project}/search?q=evidencia")
            self.assertEqual(200, got.status_code)
            self.assertEqual(1, len(got.json["items"]))
            self.assertEqual(0, got.json["provider_calls"])
            broad = self.client.get(f"/api/getangiru/project/{self.project}/search?q=%25")
            self.assertEqual([], broad.json["items"])  # Escaped LIKE wildcard
        with patch("app.auth.can_access_project", return_value=False):
            got = self.client.get(f"/api/getangiru/project/{self.project}/search?q=evidencia")
            self.assertEqual(404, got.status_code)

    def test_scope_and_missing_project(self):
        wrong_space = self.payload()
        wrong_space["space"] = "other_project"
        self.assertEqual(422, self.signed("/__getangiru/ingest", wrong_space).status_code)
        wrong_project = self.payload()
        wrong_project["project_id"] = "proj_aaaaaaaaaaaa"
        wrong_project["space"] = wrong_project["project_id"]
        self.assertEqual(404, self.signed("/__getangiru/ingest", wrong_project).status_code)

    def test_reject_oversize_and_disabled(self):
        self.assertEqual(413, self.signed("/__getangiru/ping", {"x": "a" * 7000}).status_code)
        with patch.dict(os.environ, {"GETANGIRU_MIRROR_ENABLED": "false"}):
            self.assertEqual(503, self.signed("/__getangiru/ping", {}).status_code)


if __name__ == "__main__":
    unittest.main()
