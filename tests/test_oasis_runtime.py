"""Unit tests for the low-memory OASIS factory, with zero model imports."""
from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "scripts"))
from oasis_runtime import action_concurrency, make_oasis_env


class OasisFactoryTests(unittest.TestCase):
    def setUp(self):
        self.created = []
        self.made = []
        self.channel_cls = type("Channel", (), {})

        fake = types.ModuleType("oasis")
        fake.__path__ = []
        fake.DefaultPlatformType = types.SimpleNamespace(
            TWITTER="default-twitter", REDDIT="default-reddit"
        )

        def make_platform(**kwargs):
            self.created.append(kwargs)
            return types.SimpleNamespace(channel=kwargs["channel"])

        def make_env(**kwargs):
            self.made.append(kwargs)
            return kwargs

        fake.Platform = make_platform
        fake.make = make_env
        social_platform = types.ModuleType("oasis.social_platform")
        social_platform.__path__ = []
        channel = types.ModuleType("oasis.social_platform.channel")
        channel.Channel = self.channel_cls
        self.fake_modules = {
            "oasis": fake,
            "oasis.social_platform": social_platform,
            "oasis.social_platform.channel": channel,
        }

    def test_lightweight_twitter_is_default(self):
        with patch.dict(sys.modules, self.fake_modules), patch.dict(os.environ, {
            "OASIS_TWITTER_RECSYS": "random",
            "OASIS_MAX_CONCURRENT_LLM_ACTIONS": "2",
        }):
            result = make_oasis_env(
                agent_graph="agents", platform="twitter", db_path="/tmp/test.db"
            )
        self.assertEqual(len(self.created), 1)
        self.assertEqual(self.created[0]["recsys_type"], "random")
        self.assertEqual(self.created[0]["max_rec_post_len"], 2)
        self.assertEqual(result["semaphore"], 2)
        self.assertIs(result["platform"].channel, self.created[0]["channel"])
        self.assertEqual(result["agent_graph"], "agents")

    def test_reddit_keeps_native_recommendations(self):
        with patch.dict(sys.modules, self.fake_modules), patch.dict(os.environ, {
            "OASIS_MAX_CONCURRENT_LLM_ACTIONS": "1"
        }):
            result = make_oasis_env(
                agent_graph="agents", platform="reddit", db_path="/tmp/test.db"
            )
        self.assertFalse(self.created)
        self.assertEqual(result["platform"], "default-reddit")
        self.assertEqual(result["semaphore"], 1)

    def test_embedding_modes_require_explicit_opt_in(self):
        for mode in ("twitter", "twhin-bert"):
            with self.subTest(mode=mode):
                self.created.clear()
                with patch.dict(sys.modules, self.fake_modules), patch.dict(os.environ, {
                    "OASIS_TWITTER_RECSYS": mode,
                    "OASIS_MAX_CONCURRENT_LLM_ACTIONS": "2",
                }):
                    result = make_oasis_env(
                        agent_graph="agents", platform="twitter", db_path="/tmp/test.db"
                    )
                if mode == "twhin-bert":
                    self.assertFalse(self.created)
                    self.assertEqual(result["platform"], "default-twitter")
                else:
                    self.assertEqual(self.created[0]["recsys_type"], "twitter")

    def test_invalid_modes_and_concurrency_fail_fast(self):
        with patch.dict(sys.modules, self.fake_modules), patch.dict(os.environ, {
            "OASIS_TWITTER_RECSYS": "unknown",
        }):
            with self.assertRaisesRegex(ValueError, "OASIS_TWITTER_RECSYS"):
                make_oasis_env(agent_graph="x", platform="twitter", db_path="/tmp/test.db")
        for value in ("0", "31", "hello", "-1"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "OASIS_MAX_CONCURRENT_LLM_ACTIONS": value
            }):
                with self.assertRaisesRegex(ValueError, "OASIS_MAX_CONCURRENT"):
                    action_concurrency()


if __name__ == "__main__":
    unittest.main()
