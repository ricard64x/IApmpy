"""No model download or live network needed for local model readiness tests."""
import io
import json
import unittest
from unittest.mock import patch
from flask import Flask

from app.api import graph_bp
from app.config import Config
from app.models.project import ProjectManager
from app.utils.local_model import local_inference_ready
from app.utils.llm_client import LLMClient


class LocalModelReadinessTests(unittest.TestCase):
    def setUp(self):
        app = Flask('local-model-preflight')
        app.config['TESTING'] = True
        app.register_blueprint(graph_bp, url_prefix='/api/graph')
        self.client = app.test_client()

    def test_down_model_rejected_before_project_creation(self):
        with patch.dict('os.environ', {'LLM_LOCAL_INFERENCE': 'true'}), \
             patch.object(Config, 'LLM_API_KEY', 'test-only'), \
             patch.object(Config, 'LLM_BASE_URL', 'http://127.0.0.1:18080/v1'), \
             patch('app.utils.local_model.urllib.request.build_opener') as opener, \
             patch.object(ProjectManager, 'create_project', side_effect=AssertionError('orphan project')):
            opener.return_value.open.side_effect = OSError('offline')
            r = self.client.post('/api/graph/ontology/generate',
                data={'simulation_requirement': 'Prueba ficticia',
                      'files': (io.BytesIO(b'prueba de documentos'), 'demo.txt')})
            self.assertEqual(503, r.status_code)
            self.assertEqual('LOCAL_ONTOLOGY_MODEL_UNAVAILABLE', r.json['code'])
            c = self.client.get('/api/graph/capabilities')
            self.assertFalse(c.json['data']['ontology_enabled'])
            self.assertEqual('offline', c.json['data']['ontology_model_status'])

    def test_local_json_output_is_checked_without_cpu_grammar_mode(self):
        from types import SimpleNamespace
        fake_response = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content='{"entity_types":[],"edge_types":[]}')
        )])
        with patch.dict('os.environ', {'LLM_LOCAL_INFERENCE': 'true'}), \
             patch('app.utils.llm_client.OpenAI') as fake_sdk:
            fake_sdk.return_value.chat.completions.create.return_value = fake_response
            client = LLMClient(api_key="test-key",
                               base_url="http://127.0.0.1:18080/v1", model="qwen3-4b-local")
            result = client.chat_json([{"role": "user", "content": "JSON"}], max_attempts=1)
            self.assertEqual([], result["entity_types"])
            kwargs = fake_sdk.return_value.chat.completions.create.call_args.kwargs
            self.assertNotIn("response_format", kwargs)
            self.assertEqual("qwen3-4b-local", kwargs["model"])

    def test_no_nonloopback_inference_in_local_mode(self):
        with patch.dict('os.environ', {'LLM_LOCAL_INFERENCE': 'true'}), \
             patch.object(Config, 'LLM_API_KEY', 'key'), \
             patch.object(Config, 'LLM_BASE_URL', 'https://api.openai.com/v1'):
            self.assertFalse(local_inference_ready())
            with self.assertRaisesRegex(ValueError, "modelos externos"):
                LLMClient(api_key="not-a-real-key", base_url="https://api.openai.com/v1", model="test")


if __name__ == '__main__':
    unittest.main()
