"""Regression tests for stable names and immutable simulation lineage."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.models.project import project_display_name, Project
from app.services.getangiru_native_simulation import NativeSimStore


class VersionedHistoryTests(unittest.TestCase):
    def test_auto_name_from_requirement(self):
        self.assertEqual(
            project_display_name("Unnamed Project", "Investigación de fraude en recuperación de cuentas", [], "proj_000000000001"),
            "Investigación de fraude en recuperación de cuentas",
        )
        self.assertEqual(
            project_display_name("", "", [{"filename": "incidente_keycloak.pdf"}], "proj_000000000001"),
            "incidente keycloak",
        )
        self.assertTrue(project_display_name("", "", [], "proj_000000000001").startswith("Simulación "))

    def test_legacy_project_read_does_not_replace_files(self):
        data = {"project_id": "proj_000000000001", "name": "Unnamed Project",
                "created_at": "2026-11-01", "updated_at": "2026-11-01",
                "status": "graph_completed", "simulation_requirement": "Ensayo de respuesta al incidente",
                "files": [{"filename": "evidencia.txt"}]}
        project = Project.from_dict(data)
        self.assertEqual(project.name, "Ensayo de respuesta al incidente")
        self.assertEqual(project.files, data["files"])

    def test_history_remains_and_follow_up_is_linked(self):
        with tempfile.TemporaryDirectory() as td:
            store = NativeSimStore(Path(td) / "simulations.sqlite3")
            p1 = "proj_000000000001"
            p2 = "proj_000000000002"
            graph = "gtg_" + "a" * 24
            old = store.create(project_id=p1, graph_id=graph, mode="rules", source_hash="oldhash")
            store._update(old["id"], state="completed", report_json='{"title":"Versión original"}')
            new = store.create(project_id=p1, graph_id=graph, mode="rules", source_hash="newhash",
                               parent_run_id=old["id"], instructions="Contrastar una segunda hipótesis")
            runs = store.list_project_runs(p1)
            self.assertEqual(len(runs), 2)
            self.assertEqual(store.get(old["id"])["report_json"], '{"title":"Versión original"}')
            self.assertEqual(store.get(new["id"])["parent_run_id"], old["id"])
            self.assertIn("segunda hipótesis", store.public(new["id"])["instructions"])
            with self.assertRaises(ValueError):
                store.create(project_id=p2, graph_id=graph, mode="rules", source_hash="x",
                             parent_run_id=old["id"], instructions="No permitido")
            reopened = NativeSimStore(Path(td) / "simulations.sqlite3")
            self.assertEqual(len(reopened.list_project_runs(p1)), 2)


if __name__ == "__main__":
    unittest.main()
