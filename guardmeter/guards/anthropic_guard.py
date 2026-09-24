"""Anthropic Claude guard adapter.

Uses Anthropic tool use to force a structured verdict: the model can only
respond by calling the ``classify_text`` tool, so a sample that tries to hijack
the classifier into replying in prose gets no prose channel. If the model
returns no tool call anyway (an older model, or a successful hijack), the guard
**fails closed** — see ``guardmeter.guards._verdict``.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.redact import redact
from guardmeter.core.registry import register
from guardmeter.guards._verdict import (
    CLASSIFY_INPUT_SCHEMA,
    CLASSIFY_TOOL_DESCRIPTION,
    CLASSIFY_TOOL_NAME,
    SYSTEM_PROMPT,
    VERDICT_RETRY_PROMPT,
    build_user_content,
    hijacked_result,
    verdict_from_dict,
)

logger = logging.getLogger(__name__)


def _tool_verdict(response: Any) -> dict[str, Any] | None:
    """Return the input of the first classify_text tool_use block, if any."""
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == CLASSIFY_TOOL_NAME:
            inp = getattr(block, "input", None)
            if isinstance(inp, dict):
                return inp
    return None


def _text_of(response: Any) -> str:
    """Concatenate any text blocks (fallback path for non-tool models)."""
    return "".join(getattr(b, "text", "") or "" for b in (getattr(response, "content", None) or []))


def _json_fallback(raw: str) -> dict[str, Any] | None:
    """Recover a JSON verdict object embedded in prose (models without tool use)."""
    text = raw.strip()
    for candidate in (text, _slice_braces(text)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _slice_braces(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else ""


class AnthropicGuard(Guard):
    """Guard that asks an Anthropic Claude model for a structured safety verdict.

    Raises ImportError in the constructor when the ``anthropic`` package is
    not installed.
    """

    name: str = "anthropic"
    version: str = "2.0.0"
    is_remote: bool = True

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5",
        on_parse_failure: str = "flag",
    ) -> None:
        """Initialise the guard.

        ``on_parse_failure`` controls the verdict when the model returns no
        usable tool call: ``"flag"`` (default, fail closed) or ``"pass"`` (for
        measuring the raw model). Either way the result is marked hijacked.
        """
        if on_parse_failure not in ("flag", "pass"):
            raise ValueError("on_parse_failure must be 'flag' or 'pass'")
        try:
            import anthropic  # noqa: F401
        except ImportError:
            raise ImportError(
                "anthropic package is required for AnthropicGuard. "
                "Install it with: pip install guardmeter[llm]"
            )
        import anthropic as _anthropic
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "No Anthropic API key: pass api_key= or set ANTHROPIC_API_KEY."
            )
        self._client = _anthropic.Anthropic(api_key=key)
        self.model = model
        self.on_parse_failure = on_parse_failure

    def describe(self) -> dict[str, Any]:
        """Reproducibility metadata: model, verdict mode, fail-closed policy."""
        return {"name": self.name, "version": self.version, "model": self.model,
                "mode": "tool_use", "on_parse_failure": self.on_parse_failure}

    def _create(self, messages: Any) -> Any:
        return self._client.messages.create(
            model=self.model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=[{
                "name": CLASSIFY_TOOL_NAME,
                "description": CLASSIFY_TOOL_DESCRIPTION,
                "input_schema": CLASSIFY_INPUT_SCHEMA,
            }],
            tool_choice={"type": "tool", "name": CLASSIFY_TOOL_NAME},
            messages=messages,
        )

    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Classify a single text via the Anthropic API and return a GuardResult.

        ``meta["context"]`` (prior turns or a surrounding document) is wrapped in
        <preceding_context> tags so the model can judge the message in context
        without treating either as instructions. If the first reply carries no
        verdict, one corrective follow-up turn is sent before failing closed.
        API errors propagate so the evaluator's retry/backoff can handle them.
        """
        start = time.perf_counter()
        user_content = build_user_content(text, meta.get("context"))
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]
        response = self._create(messages)
        verdict = _tool_verdict(response) or _json_fallback(_text_of(response))

        retries = 0
        if verdict is None:
            retries = 1
            messages += [
                {"role": "assistant", "content": _text_of(response) or "(no response)"},
                {"role": "user", "content": VERDICT_RETRY_PROMPT},
            ]
            response = self._create(messages)
            verdict = _tool_verdict(response) or _json_fallback(_text_of(response))

        latency_ms = int((time.perf_counter() - start) * 1000)
        result = verdict_from_dict(verdict, latency_ms) if verdict is not None else None
        if result is None:
            logger.warning("AnthropicGuard got no usable verdict after retry (hijacked): %r",
                           redact(_text_of(response))[:200])
            result = hijacked_result(latency_ms, self.on_parse_failure)
        result.metadata["verdict_retries"] = retries
        return result


register("anthropic", AnthropicGuard)
