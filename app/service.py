"""Orchestration: tie together filtering, translation, the Devin client and the store."""
from __future__ import annotations

import logging

from .config import Settings
from .devin_client import CreatedSession, DevinClient, extract_pr_url
from .models import GitHubWebhookPayload, Remediation
from .store import TERMINAL_STATUSES, Store
from .translation import build_prompt
from .webhook import should_remediate

logger = logging.getLogger("remediation")


class RemediationService:
    """Coordinates dispatching Devin sessions and tracking their progress."""

    def __init__(self, settings: Settings, store: Store, devin_client: DevinClient) -> None:
        self.settings = settings
        self.store = store
        self.devin = devin_client

    async def handle_webhook(self, payload: GitHubWebhookPayload) -> dict:
        """Process an incoming GitHub issue event.

        Returns a small dict describing the outcome (useful for the API
        response and for tests).
        """
        if not should_remediate(payload, self.settings.trigger_label):
            return {"triggered": False, "reason": "event did not match trigger rules"}

        issue = payload.issue

        # Idempotency: don't dispatch a second session for an issue that already
        # has an active (non-terminal) remediation.
        existing = self.store.get(issue.number)
        if (
            existing
            and existing.session_id
            and (existing.status or "").lower() not in TERMINAL_STATUSES
        ):
            return {
                "triggered": False,
                "reason": "remediation already in progress",
                "issue_number": issue.number,
                "session_id": existing.session_id,
            }

        prompt = build_prompt(
            issue,
            target_repo=self.settings.target_repo,
            base_branch=self.settings.default_base_branch,
            trigger_label=self.settings.trigger_label,
        )

        # Record the intent first so the dashboard reflects in-flight work even
        # if the Devin API call is slow or fails.
        record = Remediation(
            issue_number=issue.number,
            issue_title=issue.title,
            issue_url=issue.html_url,
            status="pending",
        )
        self.store.upsert(record)

        try:
            created: CreatedSession = await self.devin.create_session(prompt)
        except Exception as exc:  # noqa: BLE001 - surface any client/transport error
            logger.exception("Failed to create Devin session for issue #%s", issue.number)
            self.store.update_status(issue.number, status="error")
            return {"triggered": True, "error": str(exc), "issue_number": issue.number}

        record.session_id = created.session_id
        record.session_url = created.url
        record.status = "running"
        self.store.upsert(record)

        logger.info(
            "Dispatched Devin session %s for issue #%s", created.session_id, issue.number
        )
        return {
            "triggered": True,
            "issue_number": issue.number,
            "session_id": created.session_id,
            "session_url": created.url,
        }

    async def refresh_session(self, remediation: Remediation) -> Remediation | None:
        """Poll a single session and persist any status / PR URL changes."""
        if not remediation.session_id:
            return remediation
        try:
            data = await self.devin.get_session(remediation.session_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to poll session %s", remediation.session_id)
            return remediation

        status = (
            data.get("status_enum")
            or data.get("status")
            or remediation.status
        )
        pr_url = extract_pr_url(data) or remediation.pr_url
        return self.store.update_status(
            remediation.issue_number, status=status, pr_url=pr_url
        )

    async def poll_active_sessions(self) -> int:
        """Poll every active session once. Returns the number polled."""
        active = self.store.list_active()
        for remediation in active:
            await self.refresh_session(remediation)
        return len(active)
