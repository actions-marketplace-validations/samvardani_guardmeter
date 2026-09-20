"""Tests for secret redaction and its use in guard logging."""

from __future__ import annotations

import sys
import types

import pytest

from guardmeter.core.redact import redact

FAKE_KEY = "sk-ABCDEFGHIJKLMNOP1234567890"


def test_redact_masks_common_secret_shapes():
    assert FAKE_KEY not in redact(f"error using {FAKE_KEY} here")
    assert "REDACTED" in redact(f"error using {FAKE_KEY} here")
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("aws id AKIAIOSFODNN7EXAMPLE trailing")
    assert "abcdefgh12345678" not in redact("Authorization: Bearer abcdefgh12345678")
    assert ("deadbeef" * 8) not in redact("digest " + "deadbeef" * 8)


def test_redact_leaves_ordinary_text_alone():
    msg = "guard 'no-such-guard' not found; available: regex-baseline"
    assert redact(msg) == msg


def test_anthropic_guard_propagates_api_errors(monkeypatch):
    """The adapter no longer swallows API errors — the evaluator retries/handles
    them (and redacts on the way to the log; see test_evaluator_concurrency).
    """
    mod = types.ModuleType("anthropic")

    class _Messages:
        def create(self, **kwargs):
            raise RuntimeError(f"401 unauthorized, token={FAKE_KEY}")

    class _Client:
        def __init__(self, api_key=None):
            self.messages = _Messages()

    mod.Anthropic = _Client
    monkeypatch.setitem(sys.modules, "anthropic", mod)

    from guardmeter.guards.anthropic_guard import AnthropicGuard
    with pytest.raises(RuntimeError, match="401"):
        AnthropicGuard(api_key="x").predict("hello")


def test_redactor_masks_secret_in_error_text():
    """Whatever logs an adapter error must pass it through redact() first."""
    assert FAKE_KEY not in redact(f"401 unauthorized, token={FAKE_KEY}")
    assert "REDACTED" in redact(f"401 unauthorized, token={FAKE_KEY}")
