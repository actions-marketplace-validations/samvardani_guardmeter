"""Scenario runs surface through the serve API, snapshot, and evidence pack."""

from __future__ import annotations

import json
import threading
import urllib.request
import zipfile

import pytest

from guardmeter.scenarios.results import RunRecord, ScenarioResult, ScenarioResults
from guardmeter.serve.server import create_server
from guardmeter.store.sqlite import SQLiteStore


def _results(run_id="scn-abc12345"):
    r = ScenarioResult(
        id="s1", name="", category="support", language="en", tags=["policy"], status="pass",
        runs=[RunRecord(latency_ms=120, completion_tokens=8, passed=True, text="refund within 30 days",
                        outcomes=[{"type": "must_contain", "passed": True, "detail": "all present",
                                   "judge_disagree": False}])])
    return ScenarioResults(
        run_id=run_id, timestamp="2026-01-02T00:00:00Z", suite_name="demo", suite_version="1.0",
        target={"kind": "endpoint", "model": "llama-3.2-3b", "endpoint": "http://x/v1"},
        environment={"guardmeter_version": "0.9.0", "python_version": "3.13"}, results=[r])


def _req(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "h.db"
    store = SQLiteStore(db_path=db)
    store.save_scenario_run(_results())
    httpd = create_server("127.0.0.1", 0, store_path=str(db))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown(); httpd.server_close(); t.join(timeout=5)


def test_api_list_scenario_runs(app):
    status, body = _req(app + "/api/scenario-runs")
    assert status == 200
    runs = json.loads(body)["runs"]
    assert runs[0]["run_id"] == "scn-abc12345"
    assert runs[0]["aggregate"]["pass_rate"] == 1.0


def test_api_get_scenario_run(app):
    status, body = _req(app + "/api/scenario-runs/scn-abc12345")
    assert status == 200
    data = json.loads(body)
    assert data["suite_name"] == "demo"
    assert data["results"][0]["id"] == "s1"


def test_api_scenario_run_404(app):
    import urllib.error
    with pytest.raises(urllib.error.HTTPError) as exc:
        _req(app + "/api/scenario-runs/nope")
    assert exc.value.code == 404


def test_snapshot_includes_scenarios(tmp_path):
    from guardmeter.serve.snapshot import build_snapshot
    store = SQLiteStore(db_path=tmp_path / "h.db")
    store.save_scenario_run(_results())
    html = build_snapshot(store)
    assert "scn-abc12345" in html
    assert "scenarioRuns" in html


def test_evidence_includes_scenario_runs(tmp_path):
    from guardmeter.core.guard import Guard, GuardResult
    from guardmeter.data.schema import DatasetRecord
    from guardmeter.engine.evaluator import EvalConfig, Evaluator
    from guardmeter.report.evidence import build_evidence

    class _G(Guard):
        name = "g"

        def predict(self, text, **m):
            return GuardResult(prediction="pass", score=0.0, latency_ms=1)

    store = SQLiteStore(db_path=tmp_path / "h.db")
    ev = Evaluator(_G(), _G(), [DatasetRecord(text="a", label="benign", category="benign")],
                   EvalConfig()).run()
    store.save_run(ev)
    store.save_scenario_run(_results())
    zip_path = build_evidence(store, ev.run_id, tmp_path / "ev")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "scenario-runs.json" in names
        assert "scn-abc12345" in zf.read("scenario-runs.json").decode()
