"""Shared base for hosted safety-model guards behind an OpenAI-compatible chat API.

The NVIDIA and Ollama guard families are both thin presets over this: a single
safety model called via ``/chat/completions`` whose text reply is turned into a
flag/pass verdict by one of the parsers below. Parsers are pure and unit-tested
on real captured outputs; both families reuse them (no duplication).
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.guards._ratelimit import RateLimiter, call_with_retry

# ── Parsers: raw model content → ("flag" | "pass", score) or None ────────────
# None means "responded but unparseable" → the guard fails closed to a flag
# (never a silent pass).

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

_models_cache: dict[str, set[str]] = {}


def available_models(client: Any, base_url: str) -> set[str]:
    """Model ids listed at ``base_url`` (cached per base_url)."""
    if base_url not in _models_cache:
        _models_cache[base_url] = {m.id for m in client.models.list().data}
    return _models_cache[base_url]


class HostedSafetyGuard(Guard):
    """A single hosted safety model behind an OpenAI-compatible chat API.

    Concrete families (NVIDIA, Ollama) subclass this and supply the name,
    model id, parser kind, base_url and api key.
    """

    version: str = "1.0.0"
    is_remote: bool = True

    def __init__(
        self,
        *,
        name: str,
        model_id: str,
        kind: str,
        base_url: str,
        api_key: str,
        rpm: float | None = None,
        max_tokens: int = 128,
        on_parse_failure: str = "flag",
        resolve: bool = True,
        timeout: float = 30.0,
        not_hosted_hint: str = "",
    ) -> None:
        if kind not in PARSERS:
            raise KeyError(f"Unknown parser kind {kind!r}. Known: {sorted(PARSERS)}")
        if on_parse_failure not in ("flag", "pass"):
            raise ValueError("on_parse_failure must be 'flag' or 'pass'")
        self.name = name
        self.model_id = model_id
        self._kind = kind
        self.base_url = base_url
        self._max_tokens = max_tokens
        self.on_parse_failure = on_parse_failure
        self._limiter = RateLimiter(rpm)

        try:
            import openai as _openai
        except ImportError as e:
            raise ImportError("openai package required: pip install guardmeter[llm]") from e
        # Fail fast: our own call_with_retry owns retries, so disable the SDK's
        # internal retry (which otherwise stacks timeouts).
        self._client = _openai.OpenAI(api_key=api_key, base_url=base_url,
                                      timeout=timeout, max_retries=0)

        if resolve and model_id not in available_models(self._client, base_url):
            raise ValueError(
                f"Model {model_id!r} for {name} is not listed at {base_url}/models."
                + (f" {not_hosted_hint}" if not_hosted_hint else "")
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
