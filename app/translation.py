"""Translation layer: convert a GitHub issue into a well-scoped Devin prompt."""
from __future__ import annotations

import re

from .models import GitHubIssue

# Headings (markdown or plain) that commonly precede a list of acceptance criteria.
_ACCEPTANCE_HEADING = re.compile(
    r"^\s{0,3}#{0,6}\s*(acceptance\s+criteria|acceptance|definition\s+of\s+done)\s*:?\s*$",
    re.IGNORECASE,
)
_NEXT_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")


def branch_name(issue_number: int) -> str:
    """Branch naming convention: ``devin/issue-<number>``."""
    return f"devin/issue-{issue_number}"


def extract_acceptance_criteria(body: str | None) -> str | None:
    """Pull an "Acceptance Criteria" section out of an issue body, if present.

    Returns the section text (without the heading) or ``None`` when no such
    section exists.
    """
    if not body:
        return None

    lines = body.splitlines()
    collected: list[str] = []
    capturing = False
    for line in lines:
        if not capturing:
            if _ACCEPTANCE_HEADING.match(line):
                capturing = True
            continue
        # Stop at the next markdown heading.
        if _NEXT_HEADING.match(line):
            break
        collected.append(line)

    text = "\n".join(collected).strip()
    return text or None


def build_prompt(
    issue: GitHubIssue,
    *,
    target_repo: str,
    base_branch: str = "master",
    trigger_label: str = "devin-fix",
) -> str:
    """Build a scoped Devin session prompt from a GitHub issue.

    The prompt pins the target repo, the ``devin/issue-<number>`` branch
    convention, the acceptance criteria, and an instruction to open a PR
    against ``base_branch`` that references the issue.
    """
    branch = branch_name(issue.number)
    issue_ref = issue.html_url or f"https://github.com/{target_repo}/issues/{issue.number}"
    body = (issue.body or "").strip() or "(no description provided)"

    acceptance = extract_acceptance_criteria(issue.body)
    if acceptance:
        acceptance_block = acceptance
    else:
        acceptance_block = (
            "No explicit acceptance criteria were provided in the issue. Infer the "
            "expected behaviour from the issue title and description, and state your "
            "assumptions in the pull request description."
        )

    return f"""\
You are fixing a bug/feature request tracked by a GitHub issue.

Target repository: {target_repo}
Issue: #{issue.number} - {issue.title}
Issue URL: {issue_ref}

Issue description:
{body}

Acceptance criteria:
{acceptance_block}

Instructions:
1. Work exclusively in the `{target_repo}` repository.
2. Create a new branch named `{branch}` off of the latest `{base_branch}`.
3. Implement a minimal, focused change that satisfies the acceptance criteria above.
   Follow the repository's existing conventions, and add or update tests as appropriate.
4. Run the repository's linters and test suite, and make sure they pass.
5. Open a pull request from `{branch}` against `{base_branch}`. The PR description must
   reference this issue using a closing keyword (e.g. "Fixes #{issue.number}") so the
   issue is linked and auto-closed on merge.
6. Keep the change scoped to this issue only; do not perform unrelated refactors.

This work was triggered automatically because the issue was labeled `{trigger_label}`.
"""
