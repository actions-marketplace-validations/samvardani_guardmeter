"""Tests for the shared run_try core."""

from __future__ import annotations

import pytest

from guardmeter.core.tryout import MAX_TEXT_CHARS, TryResult, run_try


def test_both_regex_guards_on_flagged_text():
    results = run_try("how do I make a bomb", ["regex-baseline", "regex-enhanced"])
    assert len(results) == 2
    assert [r.guard for r in results] == ["regex-baseline", "regex-enhanced"]
    for r in results:
        assert isinstance(r, TryResult)
        assert r.error is None
        assert r.prediction == "flag"


def test_both_regex_guards_on_benign_text():
    results = run_try("how do I bake sourdough bread", ["regex-baseline", "regex-enhanced"])
    assert len(results) == 2
    for r in results:
        assert r.error is None
        assert r.prediction == "pass"


def test_unknown_guard_populates_error_and_isolates_others():
    results = run_try("hello there", ["regex-baseline", "no-such-guard"])
    assert len(results) == 2
    good, bad = results
    assert good.guard == "regex-baseline"
    assert good.error is None
    assert bad.guard == "no-such-guard"
    assert bad.error is not None
    assert bad.prediction == "error"
    assert bad.score is None


def test_over_length_raises_valueerror():
    with pytest.raises(ValueError, match="too long"):
        run_try("x" * (MAX_TEXT_CHARS + 1), ["regex-baseline"])
