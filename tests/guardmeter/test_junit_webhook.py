"""Tests for gate JUnit output and the failure webhook."""

from __future__ import annotations

import http.server
import json
import threading
import xml.etree.ElementTree as ET

from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.gate.checker import GateChecker
from guardmeter.gate.schema import GateConfig, GlobalThresholds
from guardmeter.gate.summary import write_junit
from guardmeter.gate.webhook import notify_webhook

_FAILING = {"min_recall": 0.99, "max_fpr": 0.0, "min_f1": 0.99, "max_latency_p99_ms": 100000}


def _check(records, guard, thresholds):
    results = Evaluator(guard, guard, records, EvalConfig()).run()
    cfg = GateConfig(global_thresholds=GlobalThresholds(**thresholds))
    return GateChecker(cfg).check(results)


def test_junit_counts_names_and_failures(sample_records, regex_enhanced, tmp_path):
    check_result = _check(sample_records, regex_enhanced, _FAILING)
    out = tmp_path / "junit.xml"
    write_junit(out, check_result)

    root = ET.parse(out).getroot()
    assert root.tag == "testsuites"
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.get("name") == "guardmeter"

    total = len(check_result.checks)
    n_fail = sum(1 for c in check_result.checks if not c.passed)
    assert total > 0
    assert n_fail > 0  # the failing config must trip some checks
    assert suite.get("tests") == str(total)
    assert suite.get("failures") == str(n_fail)

    cases = suite.findall("testcase")
    assert len(cases) == total
    assert all(" :: " in c.get("name") for c in cases)
    failing = [c for c in cases if c.find("failure") is not None]
    assert len(failing) == n_fail
    assert failing[0].find("failure").get("message")  # non-empty reason


def test_notify_webhook_posts_json():
    captured: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            captured["body"] = self.rfile.read(n).decode("utf-8")
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):  # keep test output quiet
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.handle_request, daemon=True)
    thread.start()
    try:
        ok = notify_webhook(f"http://127.0.0.1:{port}/hook",
                            {"passed": False, "run_id": "r1", "failures": []})
        thread.join(timeout=5)
        assert ok is True
        assert json.loads(captured["body"])["run_id"] == "r1"
    finally:
        httpd.server_close()


def test_notify_webhook_never_raises_on_error():
    # Port 1 is not listening; the helper must swallow the error and return False.
    assert notify_webhook("http://127.0.0.1:1/hook", {"x": 1}, timeout=1.0) is False
