#!/usr/bin/env python3
"""Simulate a GitHub webhook from a real issue.

Fetches a real issue from the GitHub REST API by number and POSTs an
equivalent ``issues`` webhook payload to the running service. This lets the
end-to-end demo work without exposing a public webhook endpoint.

Usage:
    python simulate.py <issue_number> [--action opened|labeled] \\
        [--repo owner/name] [--service http://localhost:8000] [--label devin-fix]

Environment:
    GITHUB_TOKEN   optional; raises GitHub rate limits and allows private repos
    TARGET_REPO    default repo when --repo is omitted (default acrouch8090/superset)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def fetch_issue(repo: str, number: int, token: str | None) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues/{number}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = httpx.get(url, headers=headers, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def build_event(issue: dict, repo: str, action: str, label: str) -> dict:
    """Construct an ``issues`` webhook payload from a fetched issue.

    If the issue does not already carry the trigger label we inject it so the
    simulated event matches what the real webhook would deliver.
    """
    labels = issue.get("labels") or []
    label_names = {lbl["name"] for lbl in labels if isinstance(lbl, dict)}
    if label not in label_names:
        labels = labels + [{"name": label}]

    payload: dict = {
        "action": action,
        "issue": {
            "number": issue["number"],
            "title": issue["title"],
            "body": issue.get("body"),
            "html_url": issue.get("html_url"),
            "labels": labels,
            "user": {"login": (issue.get("user") or {}).get("login", "unknown")},
        },
        "repository": {"full_name": repo},
    }
    if action == "labeled":
        payload["label"] = {"name": label}
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a GitHub issue webhook.")
    parser.add_argument("issue_number", type=int, help="Issue number to fetch")
    parser.add_argument(
        "--repo",
        default=os.environ.get("TARGET_REPO", "acrouch8090/superset"),
        help="owner/name of the repo to fetch the issue from",
    )
    parser.add_argument(
        "--action",
        default="labeled",
        choices=["opened", "labeled"],
        help="webhook action to simulate (default: labeled)",
    )
    parser.add_argument("--label", default="devin-fix", help="trigger label")
    parser.add_argument(
        "--service",
        default=os.environ.get("SERVICE_URL", "http://localhost:8000"),
        help="base URL of the running remediation service",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the payload instead of POSTing it",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or None
    print(f"Fetching issue #{args.issue_number} from {args.repo} ...", file=sys.stderr)
    issue = fetch_issue(args.repo, args.issue_number, token)
    event = build_event(issue, args.repo, args.action, args.label)

    if args.dry_run:
        print(json.dumps(event, indent=2))
        return 0

    url = f"{args.service.rstrip('/')}/webhook/github"
    print(f"POSTing simulated '{args.action}' event to {url} ...", file=sys.stderr)
    resp = httpx.post(url, json=event, timeout=60.0)
    print(f"HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except json.JSONDecodeError:
        print(resp.text)
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
