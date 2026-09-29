"""Endpoint recipes (P6): prove the scenario EndpointTarget consumes an
OpenAI-compatible webhook response, and pin the one thing it cannot do.

Every recipe in docs/ENDPOINT_RECIPES.md (OpenAI-compatible, n8n, Make, generic
HTTP) reduces to the same contract: the URL must answer POST /chat/completions
with OpenAI-shaped JSON. These tests exercise that contract against a local stub
so the recipes are verified, not just asserted.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from guardmeter.scenarios.schema import ScenarioInput
from guardmeter.scenarios.target import EndpointTarget


class _Webhook(BaseHTTPRequestHandler):
    """A stub 'workflow webhook' that answers in OpenAI chat-completions shape."""

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        user = next((m.get("content") or "" for m in reversed(body.get("messages", []))
                     if m.get("role") == "user"), "")

        if "BREAK" in user:  # generic HTTP error → TargetResponse.error, never a pass
            self.send_response(502); self.end_headers(); self.wfile.write(b"{}"); return
        if "SHAPE_WRONG" in user:  # a webhook that returns its own schema, not OpenAI's
            return self._json({"output": "hello", "meta": {"ok": True}})
        if "TOOLS" in user:  # a confirmed tool event
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "create_lead", "arguments": json.dumps({"email": "a@b.com"})}}]}
        else:
            msg = {"role": "assistant", "content": f"final output for: {user[:20]}"}
        self._json({"choices": [{"message": msg}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 7}})

    def _json(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def webhook():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Webhook)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def test_recipe_final_output_and_usage(webhook):
    """OpenAI-compatible / n8n / Make / generic: final output text and usage are read."""
    r = EndpointTarget(webhook, "wf").run(ScenarioInput(text="hello"))
    assert r.error is None
    assert r.text.startswith("final output for: hello")
    assert r.prompt_tokens == 12 and r.completion_tokens == 7


def test_recipe_confirmed_tool_event(webhook):
    """A confirmed tool call comes through as a normalised tool_calls entry."""
    r = EndpointTarget(webhook, "wf").run(ScenarioInput(text="TOOLS please"))
    assert [tc.name for tc in r.tool_calls] == ["create_lead"]
    assert r.tool_calls[0].arguments == {"email": "a@b.com"}


def test_recipe_error_is_not_a_pass(webhook):
    """A webhook 5xx becomes TargetResponse.error (excluded from pass/fail)."""
    r = EndpointTarget(webhook, "wf").run(ScenarioInput(text="BREAK it"))
    assert r.error is not None
    assert r.text == ""


def test_non_openai_shape_is_not_understood(webhook):
    """The documented gap: a webhook that returns its own schema is rejected.

    EndpointTarget does not remap response fields, so a workflow must emit the
    OpenAI shape (choices[].message). This pins that limitation.
    """
    r = EndpointTarget(webhook, "wf").run(ScenarioInput(text="SHAPE_WRONG"))
    assert r.error is not None and "no choices" in r.error
