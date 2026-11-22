"""Regression tests: environment choice, report gate and safe close semantics."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Config
from app.services.simulation_execution import (
    execution_progress, get_execution_settings, save_execution_settings,
    validate_execution_settings,
)
from app.services.simulation_runner import SimulationRunState, RunnerStatus


def run_state(platform="parallel", status=RunnerStatus.RUNNING, rounds=10, done=True, auto=False):
    return SimulationRunState(
        simulation_id="sim_unit123",
        runner_status=status, total_rounds=10,
        platform_mode=platform, auto_finalize=auto,
        twitter_current_round=rounds if platform != "reddit" else 0,
        reddit_current_round=rounds if platform != "twitter" else 0,
        twitter_completed=done and platform != "reddit",
        reddit_completed=done and platform != "twitter",
    )


class ExecutionSettingsTests(unittest.TestCase):
    def test_settings_are_persisted_and_validated(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(Config, "UPLOAD_FOLDER", tmp):
            sim_dir = Path(tmp) / "simulations" / "sim_abc123"
            sim_dir.mkdir(parents=True)
            self.assertEqual(get_execution_settings("sim_abc123")["platform"], "parallel")
            self.assertTrue(get_execution_settings("sim_abc123")["auto_finalize"])
            updated = save_execution_settings("sim_abc123", {
                "platform": "reddit", "auto_finalize": False, "max_rounds": 6,
            })
            self.assertEqual(get_execution_settings("sim_abc123"), updated)
            for payload in (
                {"platform":"tiktok"}, {"platform":"twitter","max_rounds":11},
                {"auto_finalize":"no"}, {"max_rounds":True},
            ):
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    validate_execution_settings(payload)
            with self.assertRaises(ValueError):
                get_execution_settings("../elsewhere")

    def test_waiting_is_not_completed_and_report_is_blocked(self):
        state = run_state(auto=False).to_dict()
        self.assertEqual(state["phase"], "awaiting_close")
        self.assertTrue(state["can_close_env"])
        self.assertFalse(state["can_generate_report"])
        self.assertLess(state["lifecycle_progress_percent"], 100)
        state_finalizing = run_state(auto=True).to_dict()
        self.assertEqual(state_finalizing["phase"], "finalizing")
        self.assertFalse(state_finalizing["can_generate_report"])
        state_closing = run_state(auto=False)
        state_closing.finalizing_requested = True
        self.assertEqual(state_closing.to_dict()["phase"], "finalizing")
        self.assertEqual(run_state(status=RunnerStatus.COMPLETED).to_dict()["phase"], "completed")

    def test_only_selected_platform_must_finish(self):
        twitter = run_state(platform="twitter").to_dict()
        self.assertTrue(twitter["all_rounds_completed"])
        self.assertEqual(twitter["enabled_platforms"], ["twitter"])
        self.assertEqual(twitter["phase"], "awaiting_close")
        reddit = run_state(platform="reddit").to_dict()
        self.assertTrue(reddit["all_rounds_completed"])
        both = run_state(platform="parallel", done=False).to_dict()
        self.assertEqual(both["phase"], "running_rounds")
        one_missing = run_state(platform="parallel")
        one_missing.reddit_completed = False
        self.assertFalse(one_missing.to_dict()["can_close_env"])

    def test_failed_or_early_rounds_cannot_be_finalized(self):
        failed = run_state(status=RunnerStatus.FAILED).to_dict()
        self.assertEqual(failed["phase"], "failed")
        self.assertFalse(failed["can_generate_report"])
        early = run_state(rounds=9).to_dict()
        self.assertEqual(early["phase"], "running_rounds")
        self.assertFalse(early["can_close_env"])
        state = run_state(status=RunnerStatus.STOPPING).to_dict()
        self.assertEqual(state["phase"], "finalizing")


if __name__ == "__main__":
    unittest.main()
