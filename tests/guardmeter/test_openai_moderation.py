"""Tests for the OpenAI Moderation API adapter (registered as `openai`)."""

from __future__ import annotations

import sys
import types

import pytest

from guardmeter.core.guard import GuardResult


class _Model:
    def __init__(self, d):
        self._d = d

    def model_dump(self):
        return self._d


def _install_fake_openai(monkeypatch, *, flagged, categories=None, scores=None, capture=None):
    mod = types.ModuleType("openai")

    class _Moderations:
        def create(self, **kwargs):
            if capture is not None:
                capture.update(kwargs)
            result = types.SimpleNamespace(
                flagged=flagged,
                categories=_Model(categories or {}),
                category_scores=_Model(scores or {}),
            )
            return types.SimpleNamespace(results=[result])

    class _Client:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.moderations = _Moderations()

    mod.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", mod)


def _guard(monkeypatch, **kw):
    _install_fake_openai(monkeypatch, **kw)
    from guardmeter.guards.openai_moderation import OpenAIModerationGuard
    return OpenAIModerationGuard(api_key="test-key")


def test_flagged_maps_categories(monkeypatch):
    g = _guard(monkeypatch, flagged=True,
               categories={"violence": True, "hate": False, "self-harm": True},
               scores={"violence": 0.9, "self-harm": 0.7})
    r = g.predict("hurt someone")
    assert isinstance(r, GuardResult)
    assert r.prediction == "flag"
    assert "violence" in r.categories
    assert "self_harm" in r.categories  # mapped from self-harm
    assert r.score == 0.9


def test_benign(monkeypatch):
    g = _guard(monkeypatch, flagged=False, categories={"violence": False}, scores={"violence": 0.01})
    r = g.predict("hello")
    assert r.prediction == "pass"


def test_marked_not_hijackable(monkeypatch):
    g = _guard(monkeypatch, flagged=False, scores={"violence": 0.0})
    r = g.predict("anything")
    assert r.metadata.get("hijackable") is False


def test_default_model_is_omni(monkeypatch):
    capture: dict = {}
    _install_fake_openai(monkeypatch, flagged=False, scores={"x": 0.0}, capture=capture)
    from guardmeter.guards.openai_moderation import OpenAIModerationGuard
    OpenAIModerationGuard(api_key="k").predict("hi")
    assert capture["model"] == "omni-moderation-latest"


def test_missing_package_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    from guardmeter.guards.openai_moderation import OpenAIModerationGuard
    with pytest.raises(ImportError, match=r"guardmeter\[llm\]"):
        OpenAIModerationGuard(api_key="x")


def test_missing_key_raises(monkeypatch):
    _install_fake_openai(monkeypatch, flagged=False, scores={"x": 0.0})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from guardmeter.guards.openai_moderation import OpenAIModerationGuard
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIModerationGuard()


def test_registered_as_openai():
    import guardmeter.guards.openai_moderation  # noqa: F401
    from guardmeter.core.registry import list_guards
    assert "openai" in list_guards()
