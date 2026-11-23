"""Readiness checks must fail before creating orphan projects."""
import io
import unittest
from unittest.mock import patch
from flask import Flask

from app.api import graph_bp
from app.config import Config
from app.models.project import ProjectManager


class OntologyReadinessTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask("readiness-test")
        self.app.config["TESTING"] = True
        self.app.register_blueprint(graph_bp, url_prefix="/api/graph")
        self.client = self.app.test_client()

    def test_no_model_returns_503_before_creating_project(self):
        with patch.object(Config, "LLM_API_KEY", None), patch.object(
            ProjectManager, "create_project", side_effect=AssertionError("No project should be created")
        ):
            response = self.client.post("/api/graph/ontology/generate", data={
                "simulation_requirement": "escenario ficticio",
                "files": (io.BytesIO(b"evidencia sintética"), "demo.txt"),
            })
        self.assertEqual(503, response.status_code)
        self.assertEqual("ONTOLOGY_PROVIDER_NOT_CONFIGURED", response.json["code"])
        self.assertEqual(False, response.json["success"])

    def test_capabilities_expose_flags_only_not_credentials(self):
        with patch.object(Config, "LLM_API_KEY", "a-secret-that-must-not-appear"), patch.object(
            Config, "ZEP_API_KEY", None
        ):
            response = self.client.get("/api/graph/capabilities")
        self.assertEqual(200, response.status_code)
        self.assertEqual(True, response.json["data"]["ontology_enabled"])
        self.assertEqual(False, response.json["data"]["graph_enabled"])
        self.assertNotIn("a-secret-that-must-not-appear", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
