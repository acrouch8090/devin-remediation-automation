"""Pure filtering logic for deciding whether an issue event triggers remediation."""
from __future__ import annotations

from .models import GitHubWebhookPayload


def should_remediate(payload: GitHubWebhookPayload, trigger_label: str) -> bool:
    """Return True if this issue event should dispatch a Devin remediation.

    Triggers on:
      * ``opened`` events where the issue already carries the trigger label, and
      * ``labeled`` events where the label just added is the trigger label.

    All other actions (edited, closed, unlabeled, etc.) are ignored.
    """
    action = payload.action

    if action == "labeled":
        return payload.label is not None and payload.label.name == trigger_label

    if action == "opened":
        return any(label.name == trigger_label for label in payload.issue.labels)

    return False
