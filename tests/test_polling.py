"""Tests for the polling / PR-URL extraction path (Devin mocked)."""
from __future__ import annotations

import pytest

from app.devin_client import extract_pr_url


def test_extract_pr_url_from_pull_request_object():
    data = {"pull_request": {"url": "https://github.com/acrouch8090/superset/pull/99"}}
    assert extract_pr_url(data) == "https://github.com/acrouch8090/superset/pull/99"


def test_extract_pr_url_from_structured_output():
    data = {"structured_output": {"pr_url": "https://github.com/acrouch8090/superset/pull/5"}}
    assert extract_pr_url(data) == "https://github.com/acrouch8090/superset/pull/5"


def test_extract_pr_url_absent():
    assert extract_pr_url({"status_enum": "running"}) is None
    assert extract_pr_url({}) is None


@pytest.mark.asyncio
async def test_poll_updates_status_and_pr_url(client, fake_devin):
    # Dispatch a session.
    event = {
        "action": "labeled",
        "label": {"name": "devin-fix"},
        "issue": {
            "number": 11,
            "title": "Broken thing",
            "body": "x",
            "html_url": "https://github.com/acrouch8090/superset/issues/11",
            "labels": [{"name": "devin-fix"}],
        },
    }
    client.post("/webhook/github", json=event)

    # Simulate Devin finishing with a PR.
    fake_devin.session_status["devin-session-1"] = {
        "status_enum": "finished",
        "pull_request": {"url": "https://github.com/acrouch8090/superset/pull/123"},
    }

    service = client.app.state.service
    polled = await service.poll_active_sessions()
    assert polled == 1

    record = service.store.get(11)
    assert record.status == "finished"
    assert record.pr_url == "https://github.com/acrouch8090/superset/pull/123"

    # Now terminal: no longer considered active.
    assert await service.poll_active_sessions() == 0
