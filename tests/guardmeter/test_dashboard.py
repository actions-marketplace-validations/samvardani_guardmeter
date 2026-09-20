"""Tests for DashboardGenerator (no API calls, no browser)."""

from __future__ import annotations

from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.report.generator import DashboardGenerator
from guardmeter.store.json_store import JSONFileStore


def _make_store(tmp_path):
    return JSONFileStore(dir_path=tmp_path / "runs")


def _run_eval(records, guard):
    ev = Evaluator(guard, guard, records, EvalConfig())
    return ev.run()


class TestDashboardEmpty:
    def test_empty_store_creates_file(self, tmp_path):
        store = _make_store(tmp_path)
        gen = DashboardGenerator(store)
        out = tmp_path / "dashboard.html"
        returned = gen.build(out)
        assert out.exists()
        assert returned == out

    def test_empty_store_is_valid_html(self, tmp_path):
        store = _make_store(tmp_path)
        gen = DashboardGenerator(store)
        out = tmp_path / "dashboard.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        assert "<html" in content.lower()
        assert "</html>" in content.lower()

    def test_empty_store_has_empty_runs_array(self, tmp_path):
        store = _make_store(tmp_path)
        gen = DashboardGenerator(store)
        out = tmp_path / "dashboard.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        assert "const RUNS = []" in content


class TestDashboardSingleRun:
    def test_creates_file(self, sample_records, regex_enhanced, tmp_path):
        store = _make_store(tmp_path)
        results = _run_eval(sample_records, regex_enhanced)
        store.save_run(results)

        gen = DashboardGenerator(store)
        out = tmp_path / "dash.html"
        returned = gen.build(out)
        assert out.exists()
        assert returned == out

    def test_contains_run_id(self, sample_records, regex_enhanced, tmp_path):
        store = _make_store(tmp_path)
        results = _run_eval(sample_records, regex_enhanced)
        store.save_run(results)

        gen = DashboardGenerator(store)
        out = tmp_path / "dash.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        assert results.run_id in content

    def test_default_output_path(self, sample_records, regex_enhanced, tmp_path):
        import os
        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            store = _make_store(tmp_path)
            results = _run_eval(sample_records, regex_enhanced)
            store.save_run(results)
            gen = DashboardGenerator(store)
            out = gen.build()  # should default to report/dashboard.html
            assert out.exists()
            assert out.name == "dashboard.html"
        finally:
            os.chdir(orig)

    def test_valid_html(self, sample_records, regex_enhanced, tmp_path):
        store = _make_store(tmp_path)
        results = _run_eval(sample_records, regex_enhanced)
        store.save_run(results)

        gen = DashboardGenerator(store)
        out = tmp_path / "dash.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        assert "<html" in content.lower()
        assert "</html>" in content.lower()
        assert "sea-guard Dashboard" in content


    def test_escapes_xss_in_candidate_name(self, sample_records, regex_enhanced, tmp_path):
        """A malicious guard name must never appear as live markup in the output."""
        payload = "<img src=x onerror=alert(1)>"
        store = _make_store(tmp_path)
        results = _run_eval(sample_records, regex_enhanced)
        results.candidate_name = payload
        store.save_run(results)

        gen = DashboardGenerator(store)
        out = tmp_path / "dash.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        # Embedded JSON unicode-escapes '<', so no raw active markup is emitted.
        assert "<img" not in content
        # The esc() helper exists and is applied to guard names before innerHTML.
        assert "function esc(" in content
        assert "esc(r.candidate_name)" in content


class TestDashboardMultipleRuns:
    def test_contains_all_run_ids(self, sample_records, regex_enhanced, tmp_path):
        store = _make_store(tmp_path)
        run_ids = []
        for _ in range(3):
            results = _run_eval(sample_records, regex_enhanced)
            store.save_run(results)
            run_ids.append(results.run_id)

        gen = DashboardGenerator(store)
        out = tmp_path / "dash.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        for rid in run_ids:
            assert rid in content

    def test_gate_pass_with_config(self, sample_records, regex_enhanced, tmp_path):
        store = _make_store(tmp_path)
        results = _run_eval(sample_records, regex_enhanced)
        store.save_run(results)

        gate_config = {"global_thresholds": {"min_recall": 0.0, "max_fpr": 1.0, "min_f1": 0.0}}
        gen = DashboardGenerator(store, gate_config=gate_config)
        out = tmp_path / "dash.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        # gate_pass=True should appear in serialized JSON as "gate_pass": true
        assert '"gate_pass": true' in content

    def test_gate_pass_null_without_config(self, sample_records, regex_enhanced, tmp_path):
        store = _make_store(tmp_path)
        results = _run_eval(sample_records, regex_enhanced)
        store.save_run(results)

        gen = DashboardGenerator(store)  # no gate config
        out = tmp_path / "dash.html"
        gen.build(out)
        content = out.read_text(encoding="utf-8")
        assert '"gate_pass": null' in content
