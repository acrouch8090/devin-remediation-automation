"""Tests for webhook trigger filtering (pure logic + endpoint behaviour)."""
from __future__ import annotations

from app.models import GitHubWebhookPayload
from app.webhook import should_remediate

TRIGGER = "devin-fix"


def _payload(action: str, *, labels=None, added_label=None) -> GitHubWebhookPayload:
    data = {
        "action": action,
        "issue": {
            "number": 7,
            "title": "Something broke",
            "body": "details",
            "labels": [{"name": n} for n in (labels or [])],
        },
    }
    if added_label is not None:
        data["label"] = {"name": added_label}
    return GitHubWebhookPayload.model_validate(data)


# ---- pure function ----

def test_opened_with_trigger_label_triggers():
    assert should_remediate(_payload("opened", labels=["bug", TRIGGER]), TRIGGER) is True


def test_opened_without_trigger_label_ignored():
    assert should_remediate(_payload("opened", labels=["bug"]), TRIGGER) is False


def test_labeled_with_trigger_label_triggers():
    assert should_remediate(_payload("labeled", added_label=TRIGGER), TRIGGER) is True


def test_labeled_with_other_label_ignored():
    assert should_remediate(_payload("labeled", added_label="wontfix"), TRIGGER) is False


def test_other_actions_ignored():
    for action in ("edited", "closed", "reopened", "unlabeled", "assigned"):
        assert should_remediate(_payload(action, labels=[TRIGGER]), TRIGGER) is False


# ---- endpoint behaviour with mocked Devin ----

def _event(action: str, *, labels=None, added_label=None, number=7, title="Something broke"):
    data = {
        "action": action,
        "issue": {
            "number": number,
            "title": title,
            "body": "details",
            "html_url": f"https://github.com/acrouch8090/superset/issues/{number}",
            "labels": [{"name": n} for n in (labels or [])],
        },
    }
    if added_label is not None:
        data["label"] = {"name": added_label}
    return data


def test_webhook_triggers_session_creation(client, fake_devin):
    resp = client.post("/webhook/github", json=_event("labeled", added_label=TRIGGER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["triggered"] is True
    assert body["session_id"] == "devin-session-1"
    # Exactly one session created, prompt scoped to the issue.
    assert len(fake_devin.created_prompts) == 1
    assert "devin/issue-7" in fake_devin.created_prompts[0]


def test_webhook_ignores_non_trigger_events(client, fake_devin):
    resp = client.post("/webhook/github", json=_event("opened", labels=["bug"]))
    assert resp.status_code == 200
    assert resp.json()["triggered"] is False
    assert fake_devin.created_prompts == []


def test_webhook_is_idempotent_per_issue(client, fake_devin):
    first = client.post("/webhook/github", json=_event("labeled", added_label=TRIGGER))
    assert first.json()["triggered"] is True
    # Second event for the same active issue should not create a new session.
    second = client.post("/webhook/github", json=_event("labeled", added_label=TRIGGER))
    body = second.json()
    assert body["triggered"] is False
    assert "already in progress" in body["reason"]
    assert len(fake_devin.created_prompts) == 1


def test_webhook_records_error_when_devin_fails(client, fake_devin):
    fake_devin.fail_on_create = True
    resp = client.post("/webhook/github", json=_event("labeled", added_label=TRIGGER))
    body = resp.json()
    assert body["triggered"] is True
    assert "error" in body


def test_dashboard_lists_remediation(client):
    client.post("/webhook/github", json=_event("labeled", added_label=TRIGGER, title="Fix me"))
    page = client.get("/dashboard")
    assert page.status_code == 200
    assert "Fix me" in page.text
    assert "#7" in page.text


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
