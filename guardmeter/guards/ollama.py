"""Ollama local guard family (OpenAI-compatible, http://localhost:11434/v1).

Local models, no rate limit, no API key. ``ollama:<preset>`` runs a safety model
via the same call/parse machinery as the NVIDIA family (reuses the parsers in
``_hosted``); ``ollama:chat:<model>`` runs any pulled chat model as a JSON-mode
classifier. Model ids are resolved from ``/v1/models`` at construction — a
preset whose model hasn't been pulled/imported fails with a clear message.
"""
from __future__ import annotations

import os
from typing import Any

from guardmeter.core.guard import Guard
from guardmeter.core.registry import register_resolver
from guardmeter.guards._hosted import HostedSafetyGuard

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1"
# Ollama ignores the key, but the OpenAI SDK requires a non-empty one.
OLLAMA_DUMMY_KEY = "ollama"

# preset → (ollama model tag, parser kind, max_tokens)
# The GGUF-imported presets resolve only if you've `ollama create`d them; if a
# GGUF isn't published or won't fit, the preset simply fails resolution.
PRESETS: dict[str, tuple[str, str, int]] = {
    "llama-guard3": ("llama-guard3:8b", "llamaguard", 16),
    "nemoguard-content-safety": ("nemoguard-content-safety", "nemo_json", 128),
    "nemotron-safety-guard-8b-v3": ("nemotron-safety-guard-8b-v3", "nemo_json", 128),
}


class OllamaSafetyGuard(HostedSafetyGuard):
    """A local Ollama safety model (preset over :class:`HostedSafetyGuard`)."""

    def __init__(
        self,
        preset: str,
        *,
        on_parse_failure: str = "flag",
        resolve: bool = True,
        base_url: str | None = None,
        **_ignored: Any,  # accept/ignore rpm etc. — local, no rate limit
    ) -> None:
        if preset not in PRESETS:
            raise KeyError(f"Unknown ollama preset {preset!r}. Known: {sorted(PRESETS)}")
        self.preset = preset
        model_id, kind, max_tokens = PRESETS[preset]
        super().__init__(
            name=f"ollama:{preset}", model_id=model_id, kind=kind,
            base_url=base_url or OLLAMA_BASE_URL, api_key=OLLAMA_DUMMY_KEY, rpm=None,
            max_tokens=max_tokens, on_parse_failure=on_parse_failure, resolve=resolve,
            timeout=120.0,  # local generation can be slow on first load
            not_hosted_hint="Pull it (ollama pull) or import a GGUF via a Modelfile first.",
        )


def resolve_ollama_guard(name: str, **kwargs: Any) -> Guard:
    """Factory for ``ollama:<preset>`` and ``ollama:chat:<model>`` guard names."""
    if ":" not in name:
        raise KeyError(f"Not an ollama guard name: {name!r}")
    body = name.split(":", 1)[1]
    if body.startswith("chat:"):
        model = body[len("chat:"):]
        if not model:
            raise KeyError("ollama:chat: requires a model, e.g. ollama:chat:llama3.2:3b")
        from guardmeter.guards.openai_guard import OpenAIGuard
        guard = OpenAIGuard(
            model=model, base_url=OLLAMA_BASE_URL, api_key=OLLAMA_DUMMY_KEY,
            on_parse_failure=kwargs.get("on_parse_failure", "flag"),
        )
        guard.name = f"ollama:chat:{model}"
        return guard
    return OllamaSafetyGuard(body, **kwargs)


register_resolver("ollama", resolve_ollama_guard)
