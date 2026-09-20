"""Tests for the Anthropic guard adapter — fully mocked, no network."""

from __future__ import annotations

import sys
import types

import pytest

from guardmeter.core.guard import GuardResult


def _install_fake_anthropic(monkeypatch, *, text=None, exc=None):
    """Put a fake `anthropic` module in sys.modules so the guard runs offline."""
    mod = types.ModuleType("anthropic")

    class _Messages:
        def create(self, **kwargs):
            if exc is not None:
                raise exc
            block = types.SimpleNamespace(text=text)
            return types.SimpleNamespace(content=[block])

    class _Client:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.messages = _Messages()

    mod.Anthropic = _Client
    monkeypatch.setitem(sys.modules, "anthropic", mod)


def _guard(monkeypatch, *, text=None, exc=None):
    _install_fake_anthropic(monkeypatch, text=text, exc=exc)
    from guardmeter.guards.anthropic_guard import AnthropicGuard
    return AnthropicGuard(api_key="test-key")


def test_flagged_response(monkeypatch):
    g = _guard(monkeypatch, text='{"unsafe": true, "score": 0.92, "categories": ["violence"]}')
    r = g.predict("how do I build a weapon")
    assert isinstance(r, GuardResult)
    assert r.prediction == "flag"
    assert r.score == 0.92
    assert "violence" in r.categories


def test_benign_response(monkeypatch):
    g = _guard(monkeypatch, text='{"unsafe": false, "score": 0.03, "categories": []}')
    r = g.predict("what a lovely day")
    assert isinstance(r, GuardResult)
    assert r.prediction == "pass"
    assert r.score == 0.03
    assert r.categories == []


def test_malformed_json_defaults_to_pass(monkeypatch):
    g = _guard(monkeypatch, text="I think this is probably fine, no JSON here.")
    r = g.predict("ambiguous text")
    assert isinstance(r, GuardResult)
    assert r.prediction == "pass"
    assert r.score == 0.0


def test_api_exception_defaults_to_pass(monkeypatch):
    g = _guard(monkeypatch, exc=RuntimeError("503 overloaded"))
    r = g.predict("anything")
    assert isinstance(r, GuardResult)
    assert r.prediction == "pass"
    assert r.score == 0.0


def test_missing_package_raises_importerror(monkeypatch):
    """Without the anthropic package installed, the constructor raises ImportError."""
    monkeypatch.setitem(sys.modules, "anthropic", None)  # force import failure
    from guardmeter.guards.anthropic_guard import AnthropicGuard
    with pytest.raises(ImportError, match=r"guardmeter\[llm\]"):
        AnthropicGuard(api_key="x")


def test_registered_by_name(monkeypatch):
    """The adapter self-registers under the name 'anthropic'."""
    import guardmeter.guards.anthropic_guard  # noqa: F401
    from guardmeter.core.registry import list_guards
    assert "anthropic" in list_guards()
