"""NVIDIA guard family: parsers on real captured sample outputs + resolver.

The sample strings below are verbatim responses captured from the NVIDIA-hosted
models on 2026-09-26 (via the OpenAI-compatible endpoint). No network here.
"""
from __future__ import annotations

import pytest

from guardmeter.guards import nvidia
from guardmeter.guards.nvidia import (
    PRESETS,
    NvidiaSafetyGuard,
    parse_llamaguard,
    parse_nemo_json,
    parse_nemo_text,
    resolve_nvidia_guard,
)

# Real captured outputs (nvidia/llama-3.1-nemotron-safety-guard-8b-v3, nemoguard-content, nemotron-3.5).
NEMO_JSON_UNSAFE = '{"User Safety": "unsafe", "Safety Categories": "Guns and Illegal Weapons, Criminal Planning/Confessions"} '
NEMO_JSON_SAFE = '{"User Safety": "safe"} '
NEMO_TEXT_UNSAFE = "User Safety: unsafe"
NEMO_TEXT_SAFE = "User Safety: safe"
LLAMAGUARD_UNSAFE = "unsafe\nS9"
LLAMAGUARD_SAFE = "safe"


def test_parse_nemo_json_real_outputs():
    assert parse_nemo_json(NEMO_JSON_UNSAFE) == ("flag", 0.9)
    assert parse_nemo_json(NEMO_JSON_SAFE) == ("pass", 0.1)
    assert parse_nemo_json("not json at all") is None
    assert parse_nemo_json('{"User Safety": "maybe"}') is None


def test_parse_nemo_text_real_outputs():
    assert parse_nemo_text(NEMO_TEXT_UNSAFE) == ("flag", 0.9)
    assert parse_nemo_text(NEMO_TEXT_SAFE) == ("pass", 0.1)
    assert parse_nemo_text("no verdict here") is None


def test_parse_llamaguard():
    assert parse_llamaguard(LLAMAGUARD_UNSAFE) == ("flag", 0.9)
    assert parse_llamaguard(LLAMAGUARD_SAFE) == ("pass", 0.1)
    assert parse_llamaguard("I cannot help with that") is None


def test_presets_cover_the_named_guards():
    for p in ["llama-guard-3-8b", "llama-guard-4", "nemoguard-content-safety",
              "nemoguard-topic-control", "nemotron-safety-guard-8b-v3",
              "nemotron-3.5-content-safety"]:
        assert p in PRESETS
        model_id, kind, _ = PRESETS[p]
        assert kind in ("nemo_json", "nemo_text", "llamaguard")
        assert model_id


class _FakeSafetyGuard(NvidiaSafetyGuard):
    """Bypass network construction; drive predict() through a scripted _call."""
    def __init__(self, kind: str, reply):
        self.preset = "test"
        self.name = "nvidia:test"
        self.model_id = "test/model"
        self._kind = kind
        self._max_tokens = 32
        self.on_parse_failure = "flag"
        self._reply = reply
        from guardmeter.guards._ratelimit import RateLimiter
        self._limiter = RateLimiter(None)

    def _call(self, text):
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


def test_predict_flag_pass_and_faildown():
    assert _FakeSafetyGuard("nemo_json", NEMO_JSON_UNSAFE).predict("x").prediction == "flag"
    assert _FakeSafetyGuard("nemo_json", NEMO_JSON_SAFE).predict("x").prediction == "pass"
    # Responded but unparseable → fail closed to flag (never a silent pass), hijacked.
    r = _FakeSafetyGuard("nemo_json", "garbage").predict("x")
    assert r.prediction == "flag" and r.metadata.get("hijacked") is True


def test_predict_api_error_becomes_error_not_allow():
    class Boom(Exception):
        status_code = 400  # non-retryable → immediate error result (fast)
    r = _FakeSafetyGuard("nemo_text", Boom("bad request")).predict("x")
    assert r.prediction == "error" and r.score is None  # excluded from metrics, never "pass"


def test_resolver_routes_chat_and_rejects_unknown(monkeypatch):
    # chat: delegates to the OpenAI adapter pointed at NVIDIA (no network: fake key + skip client).
    seen = {}

    class _StubOpenAI:
        def __init__(self, **kw):
            seen.update(kw)

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    import openai
    monkeypatch.setattr(openai, "OpenAI", _StubOpenAI)
    g = resolve_nvidia_guard("nvidia:chat:mistralai/mistral-large-2-instruct")
    assert g.name == "nvidia:chat:mistralai/mistral-large-2-instruct"
    assert seen["base_url"] == nvidia.NVIDIA_BASE_URL

    with pytest.raises(KeyError):
        resolve_nvidia_guard("nvidia:not-a-real-preset", resolve=False)
