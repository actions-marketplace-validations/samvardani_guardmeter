"""OpenAI guard adapter.

A chat-completions safety classifier that forces a structured verdict via
function calling and the same untrusted-data framing as the Anthropic adapter.

This replaces the previous Moderation-API adapter (0.7 and earlier): the
Moderation API classifies against OpenAI's fixed taxonomy and cannot judge
prompt-injection intent or map onto GuardMeter's category vocabulary. The
chat-based classifier can, and — like the Anthropic adapter — **fails closed**
when the model returns no usable verdict.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.registry import register
from guardmeter.guards._verdict import (
    CLASSIFY_INPUT_SCHEMA,
    CLASSIFY_TOOL_DESCRIPTION,
    CLASSIFY_TOOL_NAME,
    SYSTEM_PROMPT,
    build_user_content,
    hijacked_result,
    verdict_from_dict,
)

logger = logging.getLogger(__name__)


def _tool_arguments(response: Any) -> dict[str, Any] | None:
    """Return the parsed arguments of the first classify_text tool call, if any."""
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        return None
    for call in getattr(message, "tool_calls", None) or []:
        fn = getattr(call, "function", None)
        if fn is not None and getattr(fn, "name", None) == CLASSIFY_TOOL_NAME:
            try:
                data = json.loads(fn.arguments)
            except (json.JSONDecodeError, ValueError, TypeError):
                return None
            return data if isinstance(data, dict) else None
    return None


def _content_fallback(response: Any) -> dict[str, Any] | None:
    """Recover a JSON verdict from message content (models without tool calling)."""
    try:
        content = response.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return None
    text = content.strip()
    start, end = text.find("{"), text.rfind("}")
    for candidate in (text, text[start : end + 1] if start != -1 and end > start else ""):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


class OpenAIGuard(Guard):
    """Guard that asks an OpenAI chat model for a structured safety verdict.

    Raises ImportError in the constructor when ``openai`` is not installed.
    """

    name: str = "openai"
    version: str = "2.0.0"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        on_parse_failure: str = "flag",
    ) -> None:
        """Initialise with optional API key, chat model, and fail-closed policy."""
        if on_parse_failure not in ("flag", "pass"):
            raise ValueError("on_parse_failure must be 'flag' or 'pass'")
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAIGuard. "
                "Install it with: pip install guardmeter[llm]"
            )
        import openai as _openai
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("No OpenAI API key: pass api_key= or set OPENAI_API_KEY.")
        self._client = _openai.OpenAI(api_key=key)
        self.model = model
        self.on_parse_failure = on_parse_failure

    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Classify a single text via the OpenAI chat API and return a GuardResult."""
        start = time.perf_counter()
        user_content = build_user_content(text, meta.get("context"))
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": CLASSIFY_TOOL_NAME,
                    "description": CLASSIFY_TOOL_DESCRIPTION,
                    "parameters": CLASSIFY_INPUT_SCHEMA,
                },
            }],
            tool_choice={"type": "function", "function": {"name": CLASSIFY_TOOL_NAME}},
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        verdict = _tool_arguments(response) or _content_fallback(response)
        result = verdict_from_dict(verdict, latency_ms) if verdict is not None else None
        if result is None:
            logger.warning("OpenAIGuard got no usable verdict (hijacked)")
            return hijacked_result(latency_ms, self.on_parse_failure)
        return result


register("openai", OpenAIGuard)
