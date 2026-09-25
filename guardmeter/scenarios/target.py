"""Targets a scenario runs against: an OpenAI-compatible endpoint or a guard.

The endpoint target speaks the OpenAI chat-completions protocol (the same one
Opod serves), using only the standard library. A guard target adapts a
GuardMeter guard so block/allow-only suites can run without an LLM endpoint.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from guardmeter.core.redact import redact
from guardmeter.scenarios.schema import ScenarioInput


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class TargetResponse:
    """Normalised result of one call to a target."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    latency_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    refused: bool | None = None  # set by guard targets; endpoints infer from text
    error: str | None = None  # transport/5xx — never a pass/fail


def build_messages(inp: ScenarioInput) -> list[dict[str, Any]]:
    """Assemble the chat messages for a scenario input."""
    messages: list[dict[str, Any]] = []
    if inp.system:
        messages.append({"role": "system", "content": inp.system})
    if inp.context:
        messages.append({"role": "system", "content": f"Preceding context:\n{inp.context}"})
    if inp.messages:
        messages.extend(inp.messages)
    # Inject fake tool-output turns as an assistant tool_call + tool result pair,
    # so the model sees untrusted tool output (indirect-injection surface).
    for i, tr in enumerate(inp.tool_results or []):
        call_id = tr.get("tool_call_id") or f"call_inject_{i}"
        name = tr.get("name", "tool")
        content = tr.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content)
        messages.append({
            "role": "assistant", "content": None,
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(tr.get("args", {}))}}],
        })
        messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": content})
    if inp.text is not None:
        messages.append({"role": "user", "content": inp.text})
    return messages


class Target:
    """Base target interface."""

    def describe(self) -> dict[str, Any]:
        raise NotImplementedError

    def run(self, inp: ScenarioInput) -> TargetResponse:
        raise NotImplementedError


class EndpointTarget(Target):
    """An OpenAI-compatible chat-completions endpoint (base_url, key, model)."""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def describe(self) -> dict[str, Any]:
        return {"kind": "endpoint", "endpoint": self.base_url, "model": self.model}

    def run(self, inp: ScenarioInput) -> TargetResponse:
        messages = build_messages(inp)
        if "qwen" in self.model.lower():
            # Qwen3: skip the reasoning phase — scenarios don't need it and it's slow.
            messages = [{"role": "system", "content": "/no_think"}, *messages]
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0}
        if inp.tools:
            payload["tools"] = inp.tools
            payload["tool_choice"] = "auto"
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, headers=headers, method="POST")

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return TargetResponse(latency_ms=int((time.perf_counter() - t0) * 1000),
                                  error=redact(f"HTTP {exc.code} from {self.base_url}"))
        except Exception as exc:  # noqa: BLE001 (transport failure → error, not a verdict)
            return TargetResponse(latency_ms=int((time.perf_counter() - t0) * 1000),
                                  error=redact(str(exc)))
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if not (200 <= status < 300):
            return TargetResponse(latency_ms=latency_ms, error=f"HTTP {status}")

        return _parse_openai_response(data, latency_ms)


def _parse_openai_response(data: dict[str, Any], latency_ms: int) -> TargetResponse:
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return TargetResponse(latency_ms=latency_ms, error="malformed response (no choices)")
    text = message.get("content") or ""
    tool_calls: list[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except (json.JSONDecodeError, ValueError):
            args = {}
        tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=args if isinstance(args, dict) else {}))
    usage = data.get("usage") or {}
    return TargetResponse(
        text=text, tool_calls=tool_calls, latency_ms=latency_ms,
        prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
    )


class GuardTarget(Target):
    """Adapt a GuardMeter guard as a target for block/allow-only suites."""

    def __init__(self, guard: Any) -> None:
        self.guard = guard

    def describe(self) -> dict[str, Any]:
        d = self.guard.describe() if hasattr(self.guard, "describe") else {"name": getattr(self.guard, "name", "guard")}
        return {"kind": "guard", **d}

    def run(self, inp: ScenarioInput) -> TargetResponse:
        text = inp.text or (inp.messages[-1].get("content", "") if inp.messages else "")
        result = self.guard.predict(text, context=inp.context)
        if result.prediction == "error":
            return TargetResponse(latency_ms=result.latency_ms,
                                  error=result.metadata.get("error", "guard error"))
        return TargetResponse(text="", refused=(result.prediction == "flag"),
                              latency_ms=result.latency_ms)
