"""Runner tests against a local fake OpenAI-compatible server."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from guardmeter.scenarios import judge as judgemod
from guardmeter.scenarios.runner import run_scenario, run_suite
from guardmeter.scenarios.schema import Scenario, Suite, SuiteMeta, parse_assertion
from guardmeter.scenarios.target import EndpointTarget

_STATE = {"flaky": 0}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        user = ""
        for m in body.get("messages", []):
            if m.get("role") == "user":
                user = m.get("content") or ""
        msg: dict = {"role": "assistant", "content": ""}
        if "ERROR500" in user:
            self.send_response(500); self.end_headers(); self.wfile.write(b"{}"); return
        if "REFUSE" in user:
            msg["content"] = "I'm sorry, I can't help with that."
        elif "CALLTOOL" in user:
            msg["content"] = None
            msg["tool_calls"] = [{"id": "c1", "type": "function",
                                  "function": {"name": "send_email",
                                               "arguments": json.dumps({"to": "me@x.com"})}}]
        elif "JSONOBJ" in user:
            msg["content"] = json.dumps({"status": "ok", "count": 3})
        elif "FLAKY" in user:
            _STATE["flaky"] += 1
            msg["content"] = "yes" if _STATE["flaky"] % 2 else "no"
        else:
            msg["content"] = f"Here is the refund policy: refund within 30 days. ({user[:20]})"
        payload = {"choices": [{"message": msg}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": len((msg.get("content") or "").split())}}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def endpoint():
    _STATE["flaky"] = 0
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def _scn(id, text, expect, **kw):
    return Scenario.model_validate(
        {"id": id, "input": {"text": text}, "expect": [parse_assertion(a) for a in expect], **kw})


def _target(endpoint):
    return EndpointTarget(endpoint, "fake-model")


def test_must_contain_passes(endpoint):
    r = run_scenario(_scn("s1", "policy?", [{"must_contain": {"patterns": ["refund", "30 days"]}}]),
                     _target(endpoint), cross_check=False)
    assert r.status == "pass"


def test_must_call_tool(endpoint):
    r = run_scenario(_scn("s2", "CALLTOOL please",
                          [{"must_call_tool": {"name": "send_email", "args_match": {"to": "me@x.com"}}}]),
                     _target(endpoint), cross_check=False)
    assert r.status == "pass"


def test_must_not_call_tool_fails_when_called(endpoint):
    r = run_scenario(_scn("s3", "CALLTOOL now", [{"must_not_call_tool": {"name": "send_email"}}]),
                     _target(endpoint), cross_check=False)
    assert r.status == "fail"
    assert any("forbidden" in f for f in r.failing)


def test_refusal_and_block(endpoint):
    r = run_scenario(_scn("s4", "REFUSE this", ["block", {"refusal_expected": True}]),
                     _target(endpoint), cross_check=False)
    assert r.status == "pass"


def test_json_valid_with_schema(endpoint):
    r = run_scenario(_scn("s5", "JSONOBJ",
                          [{"json_valid": {"schema": {"type": "object", "required": ["status"]}}}]),
                     _target(endpoint), cross_check=False)
    assert r.status == "pass"


def test_must_not_contain_leak(endpoint):
    # Server never leaks, so a must_not_contain on an absent pattern passes.
    r = run_scenario(_scn("s6", "hi", [{"must_not_contain": {"patterns": ["SECRET-\\d+"]}}]),
                     _target(endpoint), cross_check=False)
    assert r.status == "pass"


def test_max_latency(endpoint):
    r = run_scenario(_scn("s7", "quick", [{"max_latency_ms": 100000}]), _target(endpoint), cross_check=False)
    assert r.status == "pass"


def test_flaky_detected(endpoint):
    r = run_scenario(_scn("s8", "FLAKY", [{"must_contain": {"patterns": ["yes"]}}], repeat=2),
                     _target(endpoint), cross_check=False)
    assert r.status == "flaky"


def test_error_case(endpoint):
    r = run_scenario(_scn("s9", "ERROR500", ["allow"]), _target(endpoint), cross_check=False)
    assert r.status == "error"
    assert r.runs[0].error is not None


def test_judge_disagree(endpoint, monkeypatch):
    # Two judges available; they disagree beyond threshold → excluded from gate.
    monkeypatch.setattr(judgemod, "pick_second_judge", lambda primary: "opod")
    scores = {"anthropic": (0.9, "good"), "opod": (0.3, "bad")}
    monkeypatch.setattr(judgemod, "score_rubric", lambda j, c, t: scores[j])
    r = run_scenario(_scn("s10", "answer", [{"rubric": {"criteria": "good", "min_score": 0.5,
                                                        "judge": "anthropic"}}]),
                     _target(endpoint), cross_check=True)
    assert r.judge_disagree is True


def test_run_suite_aggregate(endpoint):
    suite = Suite(suite=SuiteMeta(name="t"), scenarios=[
        _scn("a", "policy?", [{"must_contain": {"patterns": ["refund"]}}], category="support"),
        _scn("b", "CALLTOOL", [{"must_not_call_tool": {"name": "send_email"}}], category="agent-tools"),
    ])
    res = run_suite(suite, _target(endpoint), timestamp="2026-01-01T00:00:00Z")
    agg = res.aggregate()
    assert agg["total"] == 2
    assert agg["by_category"]["support"] == 1.0
    assert agg["by_category"]["agent-tools"] == 0.0


def test_store_round_trip(endpoint, tmp_path):
    from guardmeter.store.sqlite import SQLiteStore
    suite = Suite(suite=SuiteMeta(name="t"), scenarios=[
        _scn("a", "policy?", [{"must_contain": {"patterns": ["refund"]}}])])
    res = run_suite(suite, _target(endpoint), timestamp="2026-01-01T00:00:00Z")
    store = SQLiteStore(db_path=tmp_path / "s.db")
    store.save_scenario_run(res)
    loaded = store.get_scenario_run(res.run_id)
    assert loaded["suite_name"] == "t"
    assert loaded["aggregate"]["total"] == 1
    assert store.list_scenario_runs()[0]["run_id"] == res.run_id
