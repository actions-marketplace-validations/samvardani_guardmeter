"""Guard the scenario Action's contract (P8 PR delivery)."""

from __future__ import annotations

import pathlib
import re

import yaml

from guardmeter.decide.render import PR_COMMENT_MARKER

_ACTION = pathlib.Path(__file__).parent.parent.parent / ".github" / "actions" / "scenarios" / "action.yml"


def _action() -> dict:
    return yaml.safe_load(_ACTION.read_text(encoding="utf-8"))


def test_action_version_default_is_fixed():
    """The install default must be a real version, not the stale 0.9.0."""
    default = _action()["inputs"]["version"]["default"]
    assert default != "0.9.0"
    assert re.fullmatch(r"\d+\.\d+\.\d+", default), default


def test_action_takes_baseline_and_candidate_artifacts():
    inputs = _action()["inputs"]
    assert "baseline-run" in inputs and inputs["baseline-run"]["required"] is True
    assert "candidate-run" in inputs and inputs["candidate-run"]["required"] is True


def test_action_uses_decide_and_fails_non_approve():
    steps = _action()["runs"]["steps"]
    run_blobs = "\n".join(s.get("run", "") for s in steps)
    assert "guardmeter decide" in run_blobs
    assert "--baseline-file" in run_blobs and "--candidate-file" in run_blobs
    # A non-zero decide exit (BLOCK/INCONCLUSIVE) fails the check.
    assert 'exit "$code"' in run_blobs


def test_action_guards_fork_prs_for_the_comment():
    """The PR-comment step must not run on fork PRs (read-only token)."""
    steps = _action()["runs"]["steps"]
    comment = next(s for s in steps if s.get("name", "").startswith("Post or update PR comment"))
    cond = comment["if"]
    assert "github.event.pull_request.head.repo.full_name == github.repository" in cond
    # The comment is found/edited by the same marker the renderer emits.
    assert PR_COMMENT_MARKER in comment["run"]
