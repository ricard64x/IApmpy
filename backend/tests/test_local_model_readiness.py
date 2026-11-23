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

    def test_no_nonloopback_inference_in_local_mode(self):
        with patch.dict('os.environ', {'LLM_LOCAL_INFERENCE': 'true'}), \
             patch.object(Config, 'LLM_API_KEY', 'key'), \
             patch.object(Config, 'LLM_BASE_URL', 'https://api.openai.com/v1'):
            self.assertFalse(local_inference_ready())


if __name__ == '__main__':
    unittest.main()
