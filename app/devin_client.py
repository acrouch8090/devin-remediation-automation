"""Thin async client for the Devin API.

Only the two endpoints required by this service are implemented:
  * ``POST /v1/sessions``            - create a session
  * ``GET  /v1/session/{id}``        - poll session status

The client is intentionally small and dependency-injectable so it can be
replaced with a fake in tests (the real Devin API is never called in tests).
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class CreatedSession:
    session_id: str
    url: str | None = None


def extract_pr_url(session_data: dict) -> str | None:
    """Best-effort extraction of a PR URL from a session status response.

    The Devin API exposes the resulting pull request in a few possible shapes
    depending on version, so we check the common locations.
    """
    if not isinstance(session_data, dict):
        return None

    pr = session_data.get("pull_request")
    if isinstance(pr, dict):
        url = pr.get("url") or pr.get("html_url")
        if url:
            return url
    if isinstance(pr, str) and pr:
        return pr

    structured = session_data.get("structured_output")
    if isinstance(structured, dict):
        for key in ("pr_url", "pull_request_url", "pullRequestUrl"):
            url = structured.get(key)
            if isinstance(url, str) and url:
                return url

    return None


class DevinClient:
    """Async wrapper around the Devin REST API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.devin.ai/v1",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def create_session(self, prompt: str, *, idempotent: bool = True) -> CreatedSession:
        """Create a Devin session and return its id + URL."""
        payload: dict[str, object] = {"prompt": prompt, "idempotent": idempotent}
        resp = await self._get_client().post(
            f"{self._base_url}/sessions", json=payload, headers=self._headers
        )
        resp.raise_for_status()
        data = resp.json()
        return CreatedSession(session_id=data["session_id"], url=data.get("url"))

    async def get_session(self, session_id: str) -> dict:
        """Fetch the current status payload for a session."""
        resp = await self._get_client().get(
            f"{self._base_url}/session/{session_id}", headers=self._headers
        )
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
