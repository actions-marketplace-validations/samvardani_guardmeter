"""NVIDIA-hosted guard family.

Thin presets over the OpenAI-compatible NVIDIA endpoint
(``https://integrate.api.nvidia.com/v1``):

- ``nvidia:<preset>`` — a dedicated safety model (Llama Guard / NeMoGuard /
  Nemotron safety), sharing the parsers and call/parse machinery in ``_hosted``.
- ``nvidia:chat:<model>`` — any chat model as a JSON-mode classifier, reusing
  the OpenAI chat adapter (same hijack / fail-closed rules as the anthropic one).

Exact model ids are resolved from ``GET /v1/models`` at construction; a missing
model raises a clear error. Parsers are unit-tested on real sample outputs
(``tests/guardmeter/test_nvidia_guard.py``).
"""
from __future__ import annotations

import os
from typing import Any

from guardmeter.core.guard import Guard
from guardmeter.core.registry import register_resolver
from guardmeter.guards._hosted import (  # re-exported for tests/back-compat
    PARSERS,
    HostedSafetyGuard,
    parse_llamaguard,
    parse_nemo_json,
    parse_nemo_text,
)

__all__ = [
    "NVIDIA_BASE_URL",
    "PARSERS",
    "PRESETS",
    "NvidiaSafetyGuard",
    "parse_llamaguard",
    "parse_nemo_json",
    "parse_nemo_text",
    "resolve_nvidia_guard",
]

NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
NVIDIA_KEY_ENV = "NVIDIA_API_KEY"
DEFAULT_RPM = 35

# preset → (model id, parser kind, max_tokens)
PRESETS: dict[str, tuple[str, str, int]] = {
    "llama-guard-3-8b": ("meta/llama-guard-3-8b", "llamaguard", 16),
    "llama-guard-4": ("meta/llama-guard-4-12b", "llamaguard", 16),
    "nemoguard-content-safety": ("nvidia/llama-3.1-nemoguard-8b-content-safety", "nemo_json", 128),
    "nemoguard-topic-control": ("nvidia/llama-3.1-nemoguard-8b-topic-control", "nemo_json", 128),
    "nemotron-safety-guard-8b-v3": ("nvidia/llama-3.1-nemotron-safety-guard-8b-v3", "nemo_json", 128),
    "nemotron-3.5-content-safety": ("nvidia/nemotron-3.5-content-safety", "nemo_text", 32),
}


class NvidiaSafetyGuard(HostedSafetyGuard):
    """A single NVIDIA-hosted safety model (preset over :class:`HostedSafetyGuard`)."""

    def __init__(
        self,
        preset: str,
        *,
        rpm: float | None = DEFAULT_RPM,
        on_parse_failure: str = "flag",
        resolve: bool = True,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if preset not in PRESETS:
            raise KeyError(f"Unknown nvidia preset {preset!r}. Known: {sorted(PRESETS)}")
        self.preset = preset
        model_id, kind, max_tokens = PRESETS[preset]
        key = api_key or os.environ.get(NVIDIA_KEY_ENV)
        if not key:
            raise ValueError(f"No NVIDIA API key: set {NVIDIA_KEY_ENV}.")
        super().__init__(
            name=f"nvidia:{preset}", model_id=model_id, kind=kind,
            base_url=base_url or NVIDIA_BASE_URL, api_key=key, rpm=rpm,
            max_tokens=max_tokens, on_parse_failure=on_parse_failure, resolve=resolve,
            not_hosted_hint="It may not be hosted on this account/tier.",
        )


def resolve_nvidia_guard(name: str, **kwargs: Any) -> Guard:
    """Factory for ``nvidia:<preset>`` and ``nvidia:chat:<model>`` guard names."""
    if ":" not in name:
        raise KeyError(f"Not an nvidia guard name: {name!r}")
    body = name.split(":", 1)[1]
    if body.startswith("chat:"):
        model = body[len("chat:"):]
        if not model:
            raise KeyError("nvidia:chat: requires a model, e.g. nvidia:chat:mistralai/mistral-large-2-instruct")
        from guardmeter.guards.openai_guard import OpenAIGuard
        guard = OpenAIGuard(
            model=model, base_url=NVIDIA_BASE_URL, api_key_env=NVIDIA_KEY_ENV,
            on_parse_failure=kwargs.get("on_parse_failure", "flag"),
        )
        guard.name = f"nvidia:chat:{model}"
        return guard
    return NvidiaSafetyGuard(body, **kwargs)


register_resolver("nvidia", resolve_nvidia_guard)
