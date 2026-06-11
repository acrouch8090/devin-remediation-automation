"""Pydantic models for GitHub webhook payloads and internal records."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class GitHubLabel(BaseModel):
    name: str


class GitHubUser(BaseModel):
    login: str


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str | None = None
    html_url: str | None = None
    labels: list[GitHubLabel] = Field(default_factory=list)
    user: GitHubUser | None = None


class GitHubRepository(BaseModel):
    full_name: str | None = None


class GitHubWebhookPayload(BaseModel):
    """Subset of the GitHub ``issues`` event payload that we care about.

    Extra keys in the real payload are ignored.
    """

    action: str
    issue: GitHubIssue
    # ``label`` is only present on ``labeled`` / ``unlabeled`` events.
    label: GitHubLabel | None = None
    repository: GitHubRepository | None = None

    model_config = {"extra": "ignore"}


class Remediation(BaseModel):
    """Persisted record mapping an issue to a Devin remediation session."""

    issue_number: int
    issue_title: str
    issue_url: str | None = None
    session_id: str | None = None
    session_url: str | None = None
    status: str = "pending"
    pr_url: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
