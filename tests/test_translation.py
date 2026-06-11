"""Tests for the issue -> Devin prompt translation layer."""
from __future__ import annotations

from app.models import GitHubIssue, GitHubLabel
from app.translation import branch_name, build_prompt, extract_acceptance_criteria


def test_branch_name_convention():
    assert branch_name(123) == "devin/issue-123"


def test_extract_acceptance_criteria_markdown_heading():
    body = (
        "Some description of the bug.\n\n"
        "## Acceptance Criteria\n"
        "- The endpoint returns 200\n"
        "- A test covers the new behaviour\n\n"
        "## Notes\n"
        "irrelevant trailing section\n"
    )
    criteria = extract_acceptance_criteria(body)
    assert criteria is not None
    assert "returns 200" in criteria
    assert "test covers the new behaviour" in criteria
    # Should stop before the next heading.
    assert "irrelevant trailing section" not in criteria


def test_extract_acceptance_criteria_plain_heading():
    body = "Intro\n\nAcceptance:\n- do the thing\n"
    criteria = extract_acceptance_criteria(body)
    assert criteria is not None
    assert "do the thing" in criteria


def test_extract_acceptance_criteria_absent():
    assert extract_acceptance_criteria("just a plain description") is None
    assert extract_acceptance_criteria(None) is None
    assert extract_acceptance_criteria("") is None


def _issue(**kwargs) -> GitHubIssue:
    defaults = dict(
        number=42,
        title="Login button is misaligned",
        body=(
            "The login button overflows on mobile.\n\n"
            "## Acceptance Criteria\n- Button fits on 375px screens\n"
        ),
        html_url="https://github.com/acrouch8090/superset/issues/42",
        labels=[GitHubLabel(name="devin-fix")],
    )
    defaults.update(kwargs)
    return GitHubIssue(**defaults)


def test_build_prompt_includes_required_scope():
    prompt = build_prompt(
        _issue(),
        target_repo="acrouch8090/superset",
        base_branch="master",
        trigger_label="devin-fix",
    )
    # Target repo
    assert "acrouch8090/superset" in prompt
    # Branch convention
    assert "devin/issue-42" in prompt
    # Issue title + number
    assert "#42" in prompt
    assert "Login button is misaligned" in prompt
    # Acceptance criteria carried through
    assert "Button fits on 375px screens" in prompt
    # PR instruction referencing the issue, against the base branch
    assert "Fixes #42" in prompt
    assert "master" in prompt
    assert "pull request" in prompt.lower()


def test_build_prompt_without_acceptance_criteria_has_fallback():
    issue = _issue(body="Just a vague description with no criteria.")
    prompt = build_prompt(issue, target_repo="acrouch8090/superset")
    assert "No explicit acceptance criteria" in prompt
    # Still includes the closing-keyword instruction.
    assert "Fixes #42" in prompt
