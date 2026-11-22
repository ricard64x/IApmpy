"""Tenant and authentication regression tests for Tenonderã.

Run inside the application environment:
  python -m unittest discover -s tests -p 'test_tenondera_auth.py' -v
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import g

from app.config import Config
from app.models.project import ProjectManager
from app.services.simulation_manager import SimulationManager


class TestConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "unique-test-only-tenondera-secret-key"


class TenonderaSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.data_dir = str(Path(cls.temporary.name) / "uploads")
        cls.patchers = [
            patch.object(Config, "UPLOAD_FOLDER", cls.data_dir),
            patch.object(ProjectManager, "PROJECTS_DIR", str(Path(cls.data_dir) / "projects")),
            patch.object(SimulationManager, "SIMULATION_DATA_DIR", str(Path(cls.data_dir) / "simulations")),
            patch.dict(os.environ, {
                "APP_BASIC_AUTH_USER": "admin",
                "APP_BASIC_AUTH_PASSWORD": "initial-admin-test-password-2026",
                "OASIS_MACHINE_MEMORY_MB": "2048",
                "OASIS_MAX_PROFILES": "45",
                "OASIS_MAX_ACTIVE_AGENTS_PER_ROUND": "2",
            }),
        ]
        for p in cls.patchers:
            p.start()
        from app import create_app
        cls.app = create_app(TestConfig)

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.patchers):
            p.stop()
        cls.temporary.cleanup()

    def setUp(self):
        self.admin = self.app.test_client()
        self.other = self.app.test_client()
        self.analyst = self.app.test_client()

    @staticmethod
    def sign_in(client, username, password):
        response = client.post("/api/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.get_json()
        return response.get_json()["data"]["csrf"]

    def test_accounts_csrf_and_tenant_privacy(self):
        self.assertEqual(self.other.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.other.get("/api/graph/project/list").status_code, 401)
        csrf = self.sign_in(self.admin, "admin", "initial-admin-test-password-2026")
        # Administrator must rotate exposed bootstrap credential on first use.
        self.assertEqual(self.admin.get("/api/graph/project/list").status_code, 403)
        resp = self.admin.post("/api/auth/password", json={
            "current_password":"initial-admin-test-password-2026",
            "new_password":"rotated-admin-test-password-2026",
        }, headers={"X-CSRF-Token":csrf})
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(self.admin.get("/api/auth/me").status_code, 401)
        csrf = self.sign_in(self.admin, "admin", "rotated-admin-test-password-2026")
        self.assertEqual(self.admin.get("/api/graph/project/list").status_code, 200)
        self.assertEqual(self.admin.post("/api/auth/users", json={
            "name":"Analista Prueba", "username":"analista",
            "password":"temporary-analyst-pass-2026", "role":"analyst",
        }).status_code, 403)
        created = self.admin.post("/api/auth/users", json={
            "name":"Analista Prueba", "username":"analista",
            "password":"temporary-analyst-pass-2026", "role":"analyst",
        }, headers={"X-CSRF-Token":csrf})
        self.assertEqual(created.status_code, 201,created.get_json())
        user_id = created.get_json()["data"]["id"]
        # Unauthenticated public registration remains unavailable.
        self.assertEqual(self.other.post("/api/auth/users", json={"username":"hacker"}).status_code, 401)

        analyst_csrf=self.sign_in(self.analyst,"analista","temporary-analyst-pass-2026")
        self.assertEqual(self.analyst.get("/api/graph/project/list").status_code, 403)
        changed=self.analyst.post("/api/auth/password", json={
            "current_password":"temporary-analyst-pass-2026",
            "new_password":"secure-analyst-new-pass-2026",
        }, headers={"X-CSRF-Token":analyst_csrf})
        self.assertEqual(changed.status_code, 200,changed.get_json())
        analyst_csrf=self.sign_in(self.analyst,"analista","secure-analyst-new-pass-2026")

        # Legacy records without owners belong to the original admin only.
        legacy = ProjectManager.create_project("Legacy scenario")
        from app.auth import get_user, project_owner
        self.assertNotEqual(project_owner(legacy.project_id), user_id)
        with self.app.test_request_context("/api/graph/ontology/generate"):
            g.tenondera_user = get_user(user_id)
            owned = ProjectManager.create_project("Private analyst project")
        self.assertEqual(project_owner(owned.project_id), user_id)
        hidden=self.analyst.get("/api/graph/project/"+legacy.project_id)
        self.assertEqual(hidden.status_code,404)
        visible=self.analyst.get("/api/graph/project/"+owned.project_id)
        self.assertEqual(visible.status_code,200)
        listed=self.analyst.get("/api/graph/project/list")
        self.assertEqual(listed.status_code,200)
        self.assertEqual([x["project_id"] for x in listed.get_json()["data"]],[owned.project_id])
        admin_list=self.admin.get("/api/graph/project/list")
        self.assertEqual(admin_list.status_code,200)
        self.assertEqual(len(admin_list.get_json()["data"]),2)

        sim=SimulationManager().create_simulation(project_id=legacy.project_id,graph_id="test-graph")
        self.assertEqual(self.analyst.get("/api/simulation/"+sim.simulation_id).status_code,404)
        self.assertEqual(self.admin.get("/api/simulation/"+sim.simulation_id).status_code,200)
        cap=self.analyst.get("/api/capacity/status")
        self.assertEqual(cap.status_code,200,cap.get_json())
        self.assertEqual(cap.get_json()["data"]["recommended_max_profiles"],45)
        self.assertEqual(self.analyst.post("/api/simulation/start",json={
            "simulation_id":sim.simulation_id
        },headers={"X-CSRF-Token":analyst_csrf}).status_code,404)
        self.assertEqual(self.analyst.get("/api/auth/users").status_code,403)
        self.assertEqual(self.admin.patch("/api/auth/users/"+user_id,json={"active":False},
                                     headers={"X-CSRF-Token":csrf}).status_code,200)
        self.assertEqual(self.analyst.get("/api/auth/me").status_code,401)


if __name__ == "__main__":
    unittest.main()
