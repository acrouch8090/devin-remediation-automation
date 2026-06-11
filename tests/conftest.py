"""Shared test fixtures. The Devin API is always mocked - no real calls."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.devin_client import CreatedSession
from app.main import create_app
from app.store import Store


class FakeDevinClient:
    """In-memory stand-in for ``DevinClient``.

    Records prompts passed to ``create_session`` and returns canned session
    data from ``get_session`` so tests never touch the network.
    """

    def __init__(self) -> None:
        self.created_prompts: list[str] = []
        self._counter = 0
        # Mapping of session_id -> status payload returned by get_session.
        self.session_status: dict[str, dict] = {}
        self.fail_on_create = False

    async def create_session(self, prompt: str, *, idempotent: bool = True) -> CreatedSession:
        if self.fail_on_create:
            raise RuntimeError("simulated Devin API failure")
        self.created_prompts.append(prompt)
        self._counter += 1
        sid = f"devin-session-{self._counter}"
        self.session_status.setdefault(sid, {"status_enum": "running"})
        return CreatedSession(session_id=sid, url=f"https://app.devin.ai/sessions/{sid}")

    async def get_session(self, session_id: str) -> dict:
        return self.session_status.get(session_id, {"status_enum": "running"})

    async def aclose(self) -> None:  # pragma: no cover - nothing to close
        return None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        devin_api_key="test-key",
        target_repo="acrouch8090/superset",
        trigger_label="devin-fix",
        default_base_branch="master",
        database_path=":memory:",
    )


@pytest.fixture
def store() -> Store:
    s = Store(":memory:")
    yield s
    s.close()


@pytest.fixture
def fake_devin() -> FakeDevinClient:
    return FakeDevinClient()


@pytest.fixture
def client(settings, store, fake_devin) -> TestClient:
    app = create_app(
        settings,
        store=store,
        devin_client=fake_devin,
        enable_poller=False,
    )
    with TestClient(app) as c:
        yield c
