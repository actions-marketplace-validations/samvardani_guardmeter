"""Tests for the self-contained dashboard snapshot export."""

from __future__ import annotations

import json

from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.serve.snapshot import build_snapshot
from guardmeter.store.sqlite import SQLiteStore

_GATE = {"mode": "strict", "global_thresholds": {"min_recall": 0.0, "max_fpr": 1.0, "min_f1": 0.0, "max_latency_p99_ms": 100000}}


def _store_with_run(tmp_path, sample_records, guard):
    store = SQLiteStore(db_path=tmp_path / "history.db")
    results = Evaluator(guard, guard, sample_records, EvalConfig()).run()
    store.save_run(results)
    return store, results.run_id


def test_snapshot_is_self_contained(tmp_path, monkeypatch, sample_records, regex_enhanced):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gate.json").write_text(json.dumps(_GATE), encoding="utf-8")
    store, run_id = _store_with_run(tmp_path, sample_records, regex_enhanced)

    html = build_snapshot(store)

    # Snapshot flag + embedded app.
    assert "window.__SNAPSHOT__ = true" in html
    assert 'id="app"' in html
    # No external resource loads of any kind.
    assert "<script src" not in html.lower()
    assert 'src="http' not in html
    assert 'href="http' not in html
    assert "//cdn" not in html
    # App is inlined via an import map of data: URLs; Chart.js is present.
    assert "importmap" in html and "data:text/javascript;base64," in html
    assert "Chart" in html
    # Data is embedded (this run + its gate_pass computed against the cwd gate.json).
    assert run_id in html
    assert '"gate_pass": true' in html


def test_snapshot_gate_pass_null_without_gate(tmp_path, monkeypatch, sample_records, regex_enhanced):
    monkeypatch.chdir(tmp_path)  # no gate.json in cwd
    store, _ = _store_with_run(tmp_path, sample_records, regex_enhanced)
    html = build_snapshot(store)
    assert '"gate_pass": null' in html
