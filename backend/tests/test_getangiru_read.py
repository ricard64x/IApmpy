"""No live credentials, servers, graphs or model charges required."""
import os
import unittest
from unittest.mock import patch
import httpx
from app.services.getangiru_read import GetangiruReadClient, GetangiruUnavailable


class TestGetangiruRead(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"GETANGIRU_READ_ENABLED": "false"}):
            self.assertIsNone(GetangiruReadClient.from_environment())

    def test_rejects_insecure_or_unscoped_requests(self):
        with self.assertRaises(ValueError):
            GetangiruReadClient(base_url="http://localhost:8080", bearer_token="test")
        client = GetangiruReadClient(base_url="https://example.invalid", bearer_token="test")
        for space in ("", "../admin", "project/sibling"):
            with self.assertRaises(ValueError):
                client.search(query="hello", space=space)
        with self.assertRaises(ValueError):
            client.search(query="", space="test")

    def test_text_only_and_bounded(self):
        client = GetangiruReadClient(base_url="https://example.invalid", bearer_token="test")
        def fake_get(self, url, **kwargs):
            self_test.assertEqual(kwargs["params"]["mode"], "text")
            self_test.assertEqual(kwargs["params"]["space"], "project_123")
            req = httpx.Request("GET", url)
            return httpx.Response(200, json={"mode": "text", "items": [{"id": "1", "content": "ok", "status": "pending_llm"}]}, request=req)
        self_test = self
        with patch.object(httpx.Client, "get", fake_get):
            result = client.search(query="fact", space="project_123")
        self.assertEqual(result[0].content, "ok")

    def test_failure_is_explicit(self):
        client = GetangiruReadClient(base_url="https://example.invalid", bearer_token="test")
        with patch.object(httpx.Client, "get", side_effect=httpx.ConnectError("offline")):
            with self.assertRaises(GetangiruUnavailable):
                client.search(query="fact", space="project_123")


if __name__ == "__main__":
    unittest.main()
