"""HTTP regression tests for Plaza/Community selection and controlled close."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Config
from app.models.project import ProjectManager
from app.services.simulation_manager import SimulationManager, SimulationStatus
from app.services.simulation_runner import SimulationRunner, SimulationRunState, RunnerStatus


class QAConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "tenondera-execution-settings-qa-secret"


class ExecutionHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name) / "uploads"
        cls.patchers = [
            patch.object(Config, "UPLOAD_FOLDER", str(root)),
            patch.object(ProjectManager, "PROJECTS_DIR", str(root / "projects")),
            patch.object(SimulationManager, "SIMULATION_DATA_DIR", str(root / "simulations")),
            patch.object(SimulationRunner, "RUN_STATE_DIR", str(root / "simulations")),
            patch.dict(os.environ, {
                "APP_BASIC_AUTH_USER": "admin",
                "APP_BASIC_AUTH_PASSWORD": "tenondera-qa-bootstrap-pass",
                "LLM_API_KEY": "dummy-qa-llm",
                "ZEP_API_KEY": "dummy-qa-zep",
            }),
        ]
        for p in cls.patchers:
            p.start()
        from app import create_app
        cls.app = create_app(QAConfig)
        cls.client = cls.app.test_client()
        first = cls.client.post("/api/auth/login", json={
            "username": "admin", "password": "tenondera-qa-bootstrap-pass",
        })
        assert first.status_code == 200, first.get_json()
        csrf = first.get_json()["data"]["csrf"]
        changed = cls.client.post("/api/auth/password", json={
            "current_password": "tenondera-qa-bootstrap-pass",
            "new_password": "tenondera-qa-rotated-pass",
        }, headers={"X-CSRF-Token": csrf})
        assert changed.status_code == 200, changed.get_json()
        response = cls.client.post("/api/auth/login", json={
            "username": "admin", "password": "tenondera-qa-rotated-pass",
        })
        assert response.status_code == 200, response.get_json()
        cls.csrf = response.get_json()["data"]["csrf"]
        cls.project = ProjectManager.create_project("Test context")
        cls.sim = SimulationManager().create_simulation(
            project_id=cls.project.project_id, graph_id="unit-graph",
        )

    @classmethod
    def tearDownClass(cls):
        for patcher in reversed(cls.patchers):
            patcher.stop()
        cls.temp.cleanup()

    def test_platform_selection_is_persistent_and_not_modifiable_after_start(self):
        url = f"/api/simulation/{self.sim.simulation_id}/execution-settings"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()["data"]["auto_finalize"])
        bad = self.client.post(url, json={"platform": "instagram", "max_rounds": 10},
                               headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(bad.status_code, 400)
        saved = self.client.post(url, json={
            "platform": "reddit", "max_rounds": 6, "auto_finalize": False,
        }, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.assertEqual(self.client.get(url).get_json()["data"]["platform"], "reddit")
        meta = SimulationManager().get_simulation(self.sim.simulation_id)
        self.assertFalse(meta.enable_twitter)
        self.assertTrue(meta.enable_reddit)
        started = SimulationRunState(
            simulation_id=self.sim.simulation_id, runner_status=RunnerStatus.RUNNING,
        )
        with patch.object(SimulationRunner, "get_run_state", return_value=started):
            denied = self.client.post(url, json={
                "platform": "twitter", "max_rounds": 10,
            }, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(denied.status_code, 409)

    def test_start_rejects_one_profile_also_for_oasis(self):
        import json
        single = SimulationManager().create_simulation(
            project_id=self.project.project_id, graph_id="unit-graph")
        folder = Path(Config.UPLOAD_FOLDER) / "simulations" / single.simulation_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "reddit_profiles.json").write_text(
            json.dumps([{"user_id": 1, "name": "Único", "persona": "Ficticio"}]),
            encoding="utf-8")
        result = self.client.post("/api/simulation/start", json={
            "simulation_id": single.simulation_id, "platform": "reddit",
        }, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(result.status_code, 422, result.get_json())
        self.assertIn("2 participantes", result.get_json()["error"])
        self.assertIsNone(SimulationRunner.get_run_state(single.simulation_id))

    def test_close_ack_does_not_prematurely_mark_completed(self):
        sim = SimulationManager().get_simulation(self.sim.simulation_id)
        self.assertNotEqual(sim.status, SimulationStatus.COMPLETED)
        state = SimulationRunState(
            simulation_id=self.sim.simulation_id,
            runner_status=RunnerStatus.RUNNING,
            platform_mode="reddit", auto_finalize=False, total_rounds=6,
            reddit_current_round=6, reddit_completed=True,
        )
        self.assertEqual(state.to_dict()["phase"], "awaiting_close")
        with (
            patch.object(SimulationRunner, "get_run_state", return_value=state),
            patch.object(SimulationRunner, "close_simulation_env", return_value={"success": True, "message":"ack"}) as close,
            patch.object(SimulationRunner, "_save_run_state"),
        ):
            result = self.client.post("/api/simulation/close-env", json={
                "simulation_id": self.sim.simulation_id, "timeout": 10,
            }, headers={"X-CSRF-Token": self.csrf})
            self.assertEqual(result.status_code, 200, result.get_json())
            close.assert_called_once()
            self.assertTrue(state.finalizing_requested)
            self.assertEqual(state.to_dict()["phase"], "finalizing")
            self.assertFalse(state.to_dict()["can_generate_report"])
        actual = SimulationManager().get_simulation(self.sim.simulation_id)
        self.assertNotEqual(actual.status, SimulationStatus.COMPLETED)
        # Another close request during finalization must not dispatch IPC twice.
        with (
            patch.object(SimulationRunner, "get_run_state", return_value=state),
            patch.object(SimulationRunner, "close_simulation_env") as close,
        ):
            again = self.client.post("/api/simulation/close-env", json={
                "simulation_id": self.sim.simulation_id,
            }, headers={"X-CSRF-Token": self.csrf})
            self.assertEqual(again.status_code, 200)
            close.assert_not_called()

    def test_cannot_close_before_last_round_or_on_failed_run(self):
        for status, round_completed in [(RunnerStatus.RUNNING, False), (RunnerStatus.FAILED, True)]:
            with self.subTest(status=status):
                state = SimulationRunState(
                    simulation_id=self.sim.simulation_id,
                    runner_status=status, total_rounds=10,
                    twitter_current_round=10 if round_completed else 8,
                    reddit_current_round=10 if round_completed else 8,
                    twitter_completed=round_completed, reddit_completed=round_completed,
                )
                with (
                    patch.object(SimulationRunner, "get_run_state", return_value=state),
                    patch.object(SimulationRunner, "close_simulation_env") as close,
                ):
                    result = self.client.post("/api/simulation/close-env", json={
                        "simulation_id": self.sim.simulation_id,
                    }, headers={"X-CSRF-Token": self.csrf})
                    self.assertEqual(result.status_code, 409)
                    close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
