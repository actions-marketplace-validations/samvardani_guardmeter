"""Tests for secret redaction and its use in guard logging."""

from __future__ import annotations

import logging
import sys
import types

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


def test_fake_key_absent_from_anthropic_logs(caplog, monkeypatch):
    """A secret in an adapter exception must not survive into the log output."""
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
    with caplog.at_level(logging.WARNING):
        AnthropicGuard(api_key="x").predict("hello")

    assert FAKE_KEY not in caplog.text
    assert "REDACTED" in caplog.text
