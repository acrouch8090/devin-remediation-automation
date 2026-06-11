"""SQLite-backed persistent state store for remediations."""
from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from .models import Remediation

_SCHEMA = """
CREATE TABLE IF NOT EXISTS remediations (
    issue_number INTEGER PRIMARY KEY,
    issue_title  TEXT NOT NULL,
    issue_url    TEXT,
    session_id   TEXT,
    session_url  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    pr_url       TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""

# Session statuses that mean we no longer need to poll.
TERMINAL_STATUSES = {"finished", "completed", "stopped", "expired", "cancelled"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    """A small thread-safe wrapper over a SQLite database.

    Uses a single connection guarded by a lock. SQLite calls are fast and the
    service is low-throughput, so this keeps the implementation simple while
    remaining safe across FastAPI's worker threads and the background poller.
    """

    def __init__(self, database_path: str) -> None:
        self._path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(database_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Remediation:
        return Remediation(**dict(row))

    def get(self, issue_number: int) -> Remediation | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM remediations WHERE issue_number = ?", (issue_number,)
            ).fetchone()
        return self._row_to_model(row) if row else None

    def list_all(self) -> list[Remediation]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM remediations ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def list_active(self) -> list[Remediation]:
        """Remediations whose session is not yet in a terminal state."""
        return [
            r
            for r in self.list_all()
            if r.session_id and (r.status or "").lower() not in TERMINAL_STATUSES
        ]

    def upsert(self, remediation: Remediation) -> Remediation:
        now = _now()
        existing = self.get(remediation.issue_number)
        created_at = existing.created_at if existing else (remediation.created_at or now)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO remediations
                    (issue_number, issue_title, issue_url, session_id, session_url,
                     status, pr_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_number) DO UPDATE SET
                    issue_title = excluded.issue_title,
                    issue_url   = excluded.issue_url,
                    session_id  = excluded.session_id,
                    session_url = excluded.session_url,
                    status      = excluded.status,
                    pr_url      = excluded.pr_url,
                    updated_at  = excluded.updated_at
                """,
                (
                    remediation.issue_number,
                    remediation.issue_title,
                    remediation.issue_url,
                    remediation.session_id,
                    remediation.session_url,
                    remediation.status,
                    remediation.pr_url,
                    created_at,
                    now,
                ),
            )
            self._conn.commit()
        result = self.get(remediation.issue_number)
        assert result is not None
        return result

    def update_status(
        self,
        issue_number: int,
        *,
        status: str | None = None,
        pr_url: str | None = None,
    ) -> Remediation | None:
        existing = self.get(issue_number)
        if existing is None:
            return None
        if status is not None:
            existing.status = status
        if pr_url is not None:
            existing.pr_url = pr_url
        existing.updated_at = _now()
        return self.upsert(existing)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
