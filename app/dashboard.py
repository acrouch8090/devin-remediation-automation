"""Minimal server-rendered HTML dashboard."""
from __future__ import annotations

from html import escape

from .models import Remediation

_STATUS_COLORS = {
    "pending": "#9ca3af",
    "running": "#2563eb",
    "blocked": "#d97706",
    "finished": "#16a34a",
    "completed": "#16a34a",
    "stopped": "#6b7280",
    "expired": "#6b7280",
    "cancelled": "#6b7280",
    "error": "#dc2626",
}


def _status_badge(status: str) -> str:
    color = _STATUS_COLORS.get((status or "").lower(), "#6b7280")
    return (
        f'<span class="badge" style="background:{color}">{escape(status or "unknown")}</span>'
    )


def _link(url: str | None, text: str) -> str:
    if not url:
        return '<span class="muted">—</span>'
    return f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(text)}</a>'


def _row(r: Remediation) -> str:
    issue_cell = _link(r.issue_url, f"#{r.issue_number}")
    return f"""\
      <tr>
        <td>{issue_cell}</td>
        <td>{escape(r.issue_title)}</td>
        <td>{_status_badge(r.status)}</td>
        <td>{_link(r.session_url, "open session")}</td>
        <td>{_link(r.pr_url, "view PR")}</td>
        <td class="muted">{escape(r.updated_at)}</td>
      </tr>"""


def render_dashboard(remediations: list[Remediation], target_repo: str) -> str:
    if remediations:
        rows = "\n".join(_row(r) for r in remediations)
    else:
        rows = (
            '<tr><td colspan="6" class="muted" style="text-align:center;padding:32px">'
            "No remediations yet. Label an issue <code>devin-fix</code> to get started."
            "</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Devin Remediation Dashboard</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; background: #0b1020; color: #e5e7eb; }}
    .wrap {{ max-width: 1000px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ font-size: 20px; margin: 0 0 4px; }}
    .sub {{ color: #9ca3af; margin: 0 0 24px; font-size: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: #111827;
             border-radius: 10px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 12px 14px; font-size: 14px;
              border-bottom: 1px solid #1f2937; vertical-align: top; }}
    th {{ background: #0f172a; color: #93c5fd; font-weight: 600; font-size: 12px;
          text-transform: uppercase; letter-spacing: .04em; }}
    tr:last-child td {{ border-bottom: none; }}
    a {{ color: #60a5fa; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .muted {{ color: #6b7280; }}
    code {{ background: #1f2937; padding: 1px 6px; border-radius: 4px; }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px;
              color: #fff; font-size: 12px; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Devin Remediation Dashboard</h1>
    <p class="sub">Target repository: <code>{escape(target_repo)}</code></p>
    <table>
      <thead>
        <tr>
          <th>Issue</th>
          <th>Title</th>
          <th>Status</th>
          <th>Devin Session</th>
          <th>Pull Request</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>
  </div>
</body>
</html>"""
