"""Tests for the full serve JSON API (runs, samples, gate, datasets, jobs)."""

from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.serve.server import create_server
from guardmeter.store.sqlite import SQLiteStore

_BUILTIN = Path(__file__).parent.parent.parent / "guardmeter" / "data" / "builtin" / "sample_10.jsonl"
_GATE = {"mode": "strict", "global_thresholds": {"min_recall": 0.0, "max_fpr": 1.0, "min_f1": 0.0, "max_latency_p99_ms": 100000}}


def _req(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, dict(resp.headers), raw
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8")


@pytest.fixture
def app(tmp_path, monkeypatch, sample_records, regex_enhanced):
    monkeypatch.chdir(tmp_path)
    # gate.json + dataset in the working directory the server reads from
    (tmp_path / "gate.json").write_text(json.dumps(_GATE), encoding="utf-8")
    (tmp_path / "dataset").mkdir()
    shutil.copy(_BUILTIN, tmp_path / "dataset" / "sample_10.jsonl")

    db = tmp_path / "history.db"
    store = SQLiteStore(db_path=db)
    results = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig()).run()
    store.save_run(results)

    httpd = create_server("127.0.0.1", 0, store_path=str(db))
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", results.run_id
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_runs_includes_gate_pass(app):
    base, run_id = app
    status, _, body = _req("GET", base + "/api/runs")
    assert status == 200
    runs = json.loads(body)
    assert any(r["run_id"] == run_id for r in runs)
    assert runs[0]["gate_pass"] is True  # gate.json present → computed, not "—"


def test_runs_gate_pass_null_without_gate(app, monkeypatch, tmp_path):
    base, _ = app
    Path("gate.json").unlink()  # remove the policy from cwd
    status, _, body = _req("GET", base + "/api/runs")
    assert status == 200
    assert json.loads(body)[0]["gate_pass"] is None


def test_run_detail(app):
    base, run_id = app
    status, _, body = _req("GET", f"{base}/api/runs/{run_id}")
    assert status == 200
    assert json.loads(body)["run_id"] == run_id


def test_run_samples_and_csv(app):
    base, run_id = app
    status, _, body = _req("GET", f"{base}/api/runs/{run_id}/samples?filter=all&limit=5")
    assert status == 200
    data = json.loads(body)
    assert data["total"] >= 1 and len(data["rows"]) <= 5

    status, headers, csv_body = _req("GET", f"{base}/api/runs/{run_id}/export.csv")
    assert status == 200
    assert "text/csv" in headers["Content-Type"]
    assert "baseline_pred" in csv_body.splitlines()[0]


def test_patch_and_delete_run(app):
    base, run_id = app
    status, _, _ = _req("PATCH", f"{base}/api/runs/{run_id}", {"tag": "prod", "note": "hi"})
    assert status == 200
    _, _, body = _req("GET", base + "/api/runs")
    assert next(r for r in json.loads(body) if r["run_id"] == run_id)["tag"] == "prod"

    status, _, body = _req("DELETE", f"{base}/api/runs/{run_id}")
    assert status == 200 and json.loads(body)["deleted"] is True
    status, _, _ = _req("GET", f"{base}/api/runs/{run_id}")
    assert status == 404


def test_gate_get_evaluate_put(app):
    base, run_id = app
    status, _, body = _req("GET", base + "/api/gate")
    assert status == 200 and "global_thresholds" in json.loads(body)

    strict = {"mode": "strict", "global_thresholds": {"min_recall": 0.99, "max_fpr": 0.0, "min_f1": 0.99, "max_latency_p99_ms": 100000}}
    status, _, body = _req("POST", base + "/api/gate/evaluate", {"gate": strict, "run_id": run_id})
    assert status == 200
    result = json.loads(body)
    assert result["passed"] is False and len(result["failures"]) > 0

    status, _, _ = _req("PUT", base + "/api/gate", {"gate": strict})
    assert status == 200
    assert Path("gate.json.bak").exists()  # previous file backed up
    assert json.loads(Path("gate.json").read_text())["global_thresholds"]["min_recall"] == 0.99


def test_datasets(app):
    base, _ = app
    status, _, body = _req("GET", base + "/api/datasets")
    assert status == 200
    names = [d["name"] for d in json.loads(body)["datasets"]]
    assert "sample_10.jsonl" in names

    status, _, body = _req("GET", base + "/api/datasets/sample_10.jsonl/stats")
    assert status == 200 and "labels" in json.loads(body)

    status, _, body = _req("GET", base + "/api/datasets/sample_10.jsonl/rows?limit=3")
    assert status == 200 and len(json.loads(body)["rows"]) <= 3


def test_compare_job(app):
    base, _ = app
    status, _, body = _req("POST", base + "/api/compare",
                           {"baseline": "regex-baseline", "candidate": "regex-enhanced",
                            "dataset": "dataset/sample_10.jsonl"})
    assert status == 202
    job_id = json.loads(body)["job_id"]
    for _ in range(50):
        status, _, body = _req("GET", f"{base}/api/jobs/{job_id}")
        assert status == 200
        job = json.loads(body)
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert job["status"] == "done"
    assert job["run_id"]


def test_auth_required_for_api():
    httpd = create_server("127.0.0.1", 0, token="s3cret")
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        assert _req("GET", base + "/api/runs")[0] == 401
        assert _req("GET", base + "/api/runs", headers={"Authorization": "Bearer s3cret"})[0] == 200
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
