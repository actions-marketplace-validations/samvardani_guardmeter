"""Ollama local guard family: presets, resolver, shared-parser reuse. No network."""
from __future__ import annotations

import pytest

from guardmeter.guards import ollama
from guardmeter.guards._hosted import PARSERS
from guardmeter.guards.ollama import PRESETS, OllamaSafetyGuard, resolve_ollama_guard


def test_presets_reuse_shared_parsers():
    assert "llama-guard3" in PRESETS
    for model_id, kind, _mt in PRESETS.values():
        assert kind in PARSERS  # reuses the shared _hosted parsers, no duplication
        assert model_id


def test_safety_guard_uses_local_base_and_no_key(monkeypatch):
    seen = {}

    class _StubOpenAI:
        def __init__(self, **kw):
            seen.update(kw)

        class models:
            @staticmethod
            def list():
                return type("R", (), {"data": [type("M", (), {"id": "llama-guard3:8b"})()]})()

    import openai
    monkeypatch.setattr(openai, "OpenAI", _StubOpenAI)
    g = OllamaSafetyGuard("llama-guard3")
    assert g.name == "ollama:llama-guard3"
    assert seen["base_url"] == ollama.OLLAMA_BASE_URL
    assert seen["api_key"] == ollama.OLLAMA_DUMMY_KEY  # dummy key, no secret needed
    assert g.describe()["mode"] == "llamaguard"


def test_resolver_routes_chat_and_rejects_unknown(monkeypatch):
    class _StubOpenAI:
        def __init__(self, **kw):
            pass

    import openai
    monkeypatch.setattr(openai, "OpenAI", _StubOpenAI)
    g = resolve_ollama_guard("ollama:chat:llama3.2:3b")
    assert g.name == "ollama:chat:llama3.2:3b"

    with pytest.raises(KeyError):
        resolve_ollama_guard("ollama:not-a-preset", resolve=False)


def test_unresolved_preset_gives_clear_error(monkeypatch):
    class _StubOpenAI:
        def __init__(self, **kw):
            pass

        class models:
            @staticmethod
            def list():
                return type("R", (), {"data": []})()  # nothing pulled

    import openai
    monkeypatch.setattr(openai, "OpenAI", _StubOpenAI)
    with pytest.raises(ValueError, match="not listed"):
        OllamaSafetyGuard("nemoguard-content-safety")  # GGUF not imported
