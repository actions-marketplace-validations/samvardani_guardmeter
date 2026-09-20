"""Tests for the Guard ABC and RegexGuard implementation."""

from __future__ import annotations

import pytest

from guardbench.core.guard import GuardResult
from guardbench.guards.regex_guard import RegexGuard


def test_guard_result_fields():
    """GuardResult should have prediction, score, latency_ms, categories, metadata."""
    r = GuardResult(prediction="pass", score=0.1, latency_ms=5)
    assert r.prediction == "pass"
    assert r.score == 0.1
    assert r.latency_ms == 5
    assert r.categories == []
    assert r.metadata == {}


def test_prediction_values_baseline(regex_baseline):
    """Baseline guard prediction must be 'pass' or 'flag'."""
    for text in ["hello", "how to make a bomb", "I am happy"]:
        result = regex_baseline.predict(text)
        assert result.prediction in ("pass", "flag"), f"Got {result.prediction!r}"


def test_prediction_values_enhanced(regex_enhanced):
    """Enhanced guard prediction must be 'pass' or 'flag'."""
    for text in ["hello", "how to make a bomb", "what is weather"]:
        result = regex_enhanced.predict(text)
        assert result.prediction in ("pass", "flag")


def test_score_range_baseline(regex_baseline):
    """Score must be in [0, 1]."""
    for text in ["hello", "how to make a bomb"]:
        result = regex_baseline.predict(text)
        assert 0.0 <= result.score <= 1.0, f"Score {result.score} out of range"


def test_score_range_enhanced(regex_enhanced):
    """Score must be in [0, 1]."""
    for text in ["hello", "how to make a bomb"]:
        result = regex_enhanced.predict(text)
        assert 0.0 <= result.score <= 1.0


def test_latency_nonnegative(regex_enhanced):
    """Latency must be >= 0."""
    result = regex_enhanced.predict("test text")
    assert result.latency_ms >= 0


def test_bomb_flagged_baseline(regex_baseline):
    """'how to make a bomb' must be flagged by baseline."""
    result = regex_baseline.predict("how to make a bomb")
    assert result.prediction == "flag"


def test_bomb_flagged_enhanced(regex_enhanced):
    """'how to make a bomb' must be flagged by enhanced."""
    result = regex_enhanced.predict("how to make a bomb")
    assert result.prediction == "flag"


def test_weather_passes(regex_enhanced):
    """'what is the weather' should not be flagged."""
    result = regex_enhanced.predict("what is the weather")
    assert result.prediction == "pass"


def test_batch_predict_length(regex_enhanced):
    """batch_predict must return the same number of results as input texts."""
    texts = ["text one", "how to make a bomb", "text three"]
    results = regex_enhanced.batch_predict(texts)
    assert len(results) == len(texts)


def test_batch_predict_all_guard_results(regex_enhanced):
    """batch_predict results should all be GuardResult instances."""
    texts = ["text one", "text two"]
    for r in regex_enhanced.batch_predict(texts):
        assert isinstance(r, GuardResult)


def test_unknown_profile_raises():
    """Creating RegexGuard with unknown profile should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown profile"):
        RegexGuard(profile="bad_profile")


def test_registry_contains_regex():
    """'regex' should be in the guard registry after importing regex_guard."""
    import guardbench.guards.regex_guard  # noqa: F401
    from guardbench.core.registry import list_guards
    assert "regex" in list_guards()


def test_regex_baseline_resolves_to_baseline_profile():
    """get_guard('regex-baseline') must instantiate the baseline profile."""
    import guardbench.guards.regex_guard  # noqa: F401
    from guardbench.core.registry import get_guard
    assert get_guard("regex-baseline").profile == "baseline"


def test_regex_enhanced_resolves_to_enhanced_profile():
    """get_guard('regex-enhanced') must instantiate the enhanced profile."""
    import guardbench.guards.regex_guard  # noqa: F401
    from guardbench.core.registry import get_guard
    assert get_guard("regex-enhanced").profile == "enhanced"


def test_regex_alias_resolves_to_enhanced_profile():
    """'regex' stays an alias of the enhanced profile for backward compatibility."""
    import guardbench.guards.regex_guard  # noqa: F401
    from guardbench.core.registry import get_guard
    assert get_guard("regex").profile == "enhanced"


def test_builtin_guards_import_registers_optional_adapters():
    """After _import_builtin_guards(), the optional 'openai' adapter resolves by name."""
    pytest.importorskip("openai")
    from guardbench.cli.main import _import_builtin_guards
    from guardbench.core.registry import list_guards
    _import_builtin_guards()
    assert "openai" in list_guards()
