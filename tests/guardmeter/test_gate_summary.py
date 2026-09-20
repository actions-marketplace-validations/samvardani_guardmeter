"""Tests for gate summary writer."""

from __future__ import annotations

import json

from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.gate.checker import GateChecker, GateCheckResult
from guardmeter.gate.schema import GateConfig, GlobalThresholds
from guardmeter.gate.summary import write_markdown_summary


def _run_and_check(sample_records, guard):
    ev = Evaluator(guard, guard, sample_records, EvalConfig())
    results = ev.run()
    config = GateConfig(
        global_thresholds=GlobalThresholds(min_recall=0.0, max_fpr=1.0, max_latency_p99_ms=100000, min_f1=0.0)
    )
    checker = GateChecker(config)
    check_result = checker.check(results)
    return results, config, check_result


def test_markdown_file_created(sample_records, regex_enhanced, tmp_path):
    """write_markdown_summary should create a .md file."""
    results, config, check_result = _run_and_check(sample_records, regex_enhanced)
    out = tmp_path / "ci_summary.md"
    write_markdown_summary(check_result, results, config, out)
    assert out.exists()


def test_json_file_created(sample_records, regex_enhanced, tmp_path):
    """write_markdown_summary should also create a companion .json file."""
    results, config, check_result = _run_and_check(sample_records, regex_enhanced)
    out = tmp_path / "ci_summary.md"
    write_markdown_summary(check_result, results, config, out)
    json_path = tmp_path / "ci_summary.json"
    assert json_path.exists()


def test_json_contains_run_id(sample_records, regex_enhanced, tmp_path):
    """JSON summary should include the run_id."""
    results, config, check_result = _run_and_check(sample_records, regex_enhanced)
    out = tmp_path / "ci_summary.md"
    write_markdown_summary(check_result, results, config, out)
    data = json.loads((tmp_path / "ci_summary.json").read_text())
    assert data["run_id"] == results.run_id


def test_markdown_contains_table(sample_records, regex_enhanced, tmp_path):
    """Markdown summary should contain a table."""
    results, config, check_result = _run_and_check(sample_records, regex_enhanced)
    out = tmp_path / "ci_summary.md"
    write_markdown_summary(check_result, results, config, out)
    content = out.read_text(encoding="utf-8")
    assert "|" in content  # table separator


def test_failed_summary_includes_failure(sample_records, regex_enhanced, tmp_path):
    """Failed gate summary should list failures."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    config = GateConfig(
        global_thresholds=GlobalThresholds(min_recall=1.0, max_fpr=0.0, max_latency_p99_ms=0, min_f1=1.0)
    )
    check_result = GateCheckResult(passed=False, failures=["something failed"])
    out = tmp_path / "ci_summary.md"
    write_markdown_summary(check_result, results, config, out)
    content = out.read_text(encoding="utf-8")
    assert "something failed" in content
