"""Optional, read-only Getangiru text retrieval. Disabled unless explicitly configured.

Never sends a user document to Getangiru. Graphiti writes and model inference
are intentionally out of scope until network/auth, privacy and quality gates pass.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

_SPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class GetangiruUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class GetangiruResult:
    id: str
    content: str
    status: str


class GetangiruReadClient:
    """Per-project authenticated text lookup; caller enforces authorization."""

    def __init__(self, *, base_url: str, bearer_token: str, timeout: float = 2.0):
        url = urlparse(base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Getangiru endpoint must be a clean HTTPS URL")
        if not bearer_token or len(bearer_token) > 200:
            raise ValueError("Getangiru tenant token is required")
        if not 0 < timeout <= 10:
            raise ValueError("Getangiru timeout must be 0 < timeout <= 10 seconds")
        self._base_url, self._token, self._timeout = base_url.rstrip("/"), bearer_token, timeout

    @classmethod
    def from_environment(cls):
        if os.getenv("GETANGIRU_READ_ENABLED", "false").lower() != "true":
            return None
        url = os.getenv("GETANGIRU_BASE_URL", "")
        token = os.getenv("GETANGIRU_TENANT_TOKEN", "")
        return cls(base_url=url, bearer_token=token)

    def search(self, *, query: str, space: str, limit: int = 8) -> list[GetangiruResult]:
        if not _SPACE.fullmatch(space):
            raise ValueError("Invalid Getangiru space")
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError("Query must be between 1 and 256 characters")
        if not 1 <= limit <= 25:
            raise ValueError("Limit must be 1..25")
        # No retry: protect budget/latency and never silently fall back across tenants.
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=False, trust_env=False) as client:
                response = client.get(
                    self._base_url + "/v1/memories/search",
                    params={"q": query, "space": space, "mode": "text", "limit": limit},
                    headers={"Authorization": "Bearer " + self._token},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GetangiruUnavailable("Getangiru read unavailable") from exc
        if not isinstance(payload, dict) or payload.get("mode") != "text" or not isinstance(payload.get("items"), list):
            raise GetangiruUnavailable("Invalid Getangiru response")
        output = []
        for item in payload["items"][:limit]:
            if not isinstance(item, dict) or not isinstance(item.get("content"), str):
                raise GetangiruUnavailable("Invalid Getangiru item")
            output.append(GetangiruResult(id=str(item.get("id", "")), content=item["content"][:4000], status=str(item.get("status", ""))))
        return output
