"""NVIDIA-hosted guard family.

Thin presets over the OpenAI-compatible NVIDIA endpoint
(``https://integrate.api.nvidia.com/v1``):

- ``nvidia:<preset>`` — a dedicated safety model (Llama Guard / NeMoGuard /
  Nemotron safety), each with its own prompt/parse below.
- ``nvidia:chat:<model>`` — any chat model as a JSON-mode classifier, reusing
  the OpenAI chat adapter (same hijack / fail-closed rules as the anthropic one).

Exact model ids are resolved from ``GET /v1/models`` at construction; a missing
model raises a clear error. Every prompt/parse lives in one place with a unit
test on real sample outputs (``tests/guardmeter/test_nvidia_guard.py``).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.registry import register_resolver
from guardmeter.guards._ratelimit import RateLimiter, call_with_retry

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
NVIDIA_KEY_ENV = "NVIDIA_API_KEY"
DEFAULT_RPM = 35


# ── Parsers: raw model content → ("flag" | "pass", score) or None ────────────
# None means "responded but unparseable" → the guard fails closed to a flag
# (never a silent pass). Kept pure and side-effect free so they can be unit
# tested directly on captured sample outputs.

def parse_nemo_json(content: str) -> tuple[str, float] | None:
    """NeMoGuard / Nemotron-safety JSON: {"User Safety": "unsafe"|"safe", ...}."""
    try:
        data = json.loads(content.strip())
    except (ValueError, TypeError):
        return None
    verdict = str(data.get("User Safety", "")).strip().lower()
    if verdict == "unsafe":
        return "flag", 0.9
    if verdict == "safe":
        return "pass", 0.1
    return None


def parse_nemo_text(content: str) -> tuple[str, float] | None:
    """Nemotron-3.5-content plain text: 'User Safety: unsafe' / 'User Safety: safe'."""
    m = re.search(r"user\s*safety\s*:\s*(unsafe|safe)", content, re.IGNORECASE)
    if not m:
        return None
    return ("flag", 0.9) if m.group(1).lower() == "unsafe" else ("pass", 0.1)


def parse_llamaguard(content: str) -> tuple[str, float] | None:
    """Llama Guard: first token 'safe' or 'unsafe' (followed by categories)."""
    c = content.strip().lower()
    if c.startswith("unsafe"):
        return "flag", 0.9
    if c.startswith("safe"):
        return "pass", 0.1
    return None


PARSERS = {
    "nemo_json": parse_nemo_json,
    "nemo_text": parse_nemo_text,
    "llamaguard": parse_llamaguard,
}

# preset → (model id, parser kind, max_tokens)
PRESETS: dict[str, tuple[str, str, int]] = {
    "llama-guard-3-8b": ("meta/llama-guard-3-8b", "llamaguard", 16),
    "llama-guard-4": ("meta/llama-guard-4-12b", "llamaguard", 16),
    "nemoguard-content-safety": ("nvidia/llama-3.1-nemoguard-8b-content-safety", "nemo_json", 128),
    "nemoguard-topic-control": ("nvidia/llama-3.1-nemoguard-8b-topic-control", "nemo_json", 128),
    "nemotron-safety-guard-8b-v3": ("nvidia/llama-3.1-nemotron-safety-guard-8b-v3", "nemo_json", 128),
    "nemotron-3.5-content-safety": ("nvidia/nemotron-3.5-content-safety", "nemo_text", 32),
}

_models_cache: dict[str, set[str]] = {}


def _available_models(client: Any, base_url: str) -> set[str]:
    if base_url not in _models_cache:
        _models_cache[base_url] = {m.id for m in client.models.list().data}
    return _models_cache[base_url]


class NvidiaSafetyGuard(Guard):
    """A single NVIDIA-hosted safety model behind the chat-completions API."""

    version: str = "1.0.0"
    is_remote: bool = True

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
        if on_parse_failure not in ("flag", "pass"):
            raise ValueError("on_parse_failure must be 'flag' or 'pass'")
        self.preset = preset
        self.name = f"nvidia:{preset}"
        self.model_id, self._kind, self._max_tokens = PRESETS[preset]
        self.on_parse_failure = on_parse_failure
        self._limiter = RateLimiter(rpm)
        self.base_url = base_url or NVIDIA_BASE_URL

        try:
            import openai as _openai
        except ImportError as e:
            raise ImportError("openai package required: pip install guardmeter[llm]") from e
        key = api_key or os.environ.get(NVIDIA_KEY_ENV)
        if not key:
            raise ValueError(f"No NVIDIA API key: set {NVIDIA_KEY_ENV}.")
        # Fail fast: our own call_with_retry owns retries, so disable the SDK's
        # internal retry (which otherwise stacks timeouts into ~75s per call).
        self._client = _openai.OpenAI(api_key=key, base_url=self.base_url,
                                      timeout=30, max_retries=0)

        if resolve and self.model_id not in _available_models(self._client, self.base_url):
            raise ValueError(
                f"Model {self.model_id!r} for nvidia:{preset} is not listed at "
                f"{self.base_url}/models — it may not be hosted on this account/tier."
            )

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "model": self.model_id,
                "mode": self._kind, "base_url": self.base_url,
                "on_parse_failure": self.on_parse_failure}

    def _call(self, text: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": text}],
            max_tokens=self._max_tokens,
            temperature=0,
        )
        return resp.choices[0].message.content or ""

    def predict(self, text: str, **meta: Any) -> GuardResult:
        start = time.perf_counter()
        try:
            content = call_with_retry(lambda: self._call(text), limiter=self._limiter)
        except Exception as exc:  # noqa: BLE001 — API failure → excluded error, never allow
            from guardmeter.core.redact import redact
            latency_ms = int((time.perf_counter() - start) * 1000)
            return GuardResult(prediction="error", score=None, latency_ms=latency_ms,
                               metadata={"error": redact(str(exc))})
        latency_ms = int((time.perf_counter() - start) * 1000)
        parsed = PARSERS[self._kind](content)
        if parsed is None:
            # Responded but unparseable → fail closed (default flag), mark hijacked.
            pred = "flag" if self.on_parse_failure == "flag" else "pass"
            return GuardResult(prediction=pred, score=0.5, latency_ms=latency_ms,
                               metadata={"hijacked": True, "raw": content[:200]})
        prediction, score = parsed
        return GuardResult(prediction=prediction, score=score, latency_ms=latency_ms)


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
