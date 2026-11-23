"""Health-gated, loopback-only local inference configuration.

The local model never needs access to user records or public IP connectivity.
Only localhost:18080 may be used when LLM_LOCAL_INFERENCE=true.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request

from ..config import Config

LOCAL_LLM_BASE_URL = "http://127.0.0.1:18080/v1"


def local_inference_requested() -> bool:
    return os.environ.get("LLM_LOCAL_INFERENCE", "false").lower() == "true"


def local_inference_ready() -> bool:
    if not local_inference_requested():
        return bool(Config.LLM_API_KEY)
    if not Config.LLM_API_KEY or Config.LLM_BASE_URL.rstrip("/") != LOCAL_LLM_BASE_URL:
        return False
    try:
        # Model health check never sends user data and never follows
        # non-local redirects. /health is the llama.cpp server endpoint.
        request = urllib.request.Request("http://127.0.0.1:18080/health")
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(request, timeout=1.2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def ontology_model_status() -> str:
    if not Config.LLM_API_KEY:
        return "not_configured"
    if local_inference_requested():
        return "ready" if local_inference_ready() else "offline"
    return "configured_not_tested"
