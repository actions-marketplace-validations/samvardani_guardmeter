"""Tests for the Click CLI."""

from __future__ import annotations

import json
import pathlib

import pytest
from click.testing import CliRunner

from guardmeter.cli.main import cli

_BUILTIN = (
    pathlib.Path(__file__).parent.parent.parent
    / "guardmeter" / "data" / "builtin" / "sample_10.jsonl"
)


@pytest.fixture
def runner():
    return CliRunner()


def _compare(runner, tmp_path, extra=None):
    """Run a compare into a fresh store and return (result, db_path)."""
    db = tmp_path / "test.db"
    args = [
        "compare", "--baseline", "regex-baseline", "--candidate", "regex-enhanced",
        "--dataset", str(_BUILTIN), "--store", str(db),
    ] + (extra or [])
    return runner.invoke(cli, args), db


def test_help_exits_zero(runner):
    """guardmeter --help should exit 0."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0, result.output


def test_compare_help(runner):
    """guardmeter compare --help should exit 0."""
    result = runner.invoke(cli, ["compare", "--help"])
    assert result.exit_code == 0


def test_report_help(runner):
    """guardmeter report --help should exit 0."""
    result = runner.invoke(cli, ["report", "--help"])
    assert result.exit_code == 0


def test_gate_help(runner):
    """guardmeter gate --help should exit 0."""
    result = runner.invoke(cli, ["gate", "--help"])
    assert result.exit_code == 0


def test_runs_list_empty_store(runner, tmp_path):
    """runs list on an empty store should exit 0."""
    db = tmp_path / "test.db"
    result = runner.invoke(cli, ["runs", "list", "--store", str(db)])
    assert result.exit_code == 0


def test_init_creates_files(runner, tmp_path):
    """init should create gate.json and the CSV dataset the README uses (no config.yaml)."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, result.output
        assert pathlib.Path("gate.json").exists()
        assert pathlib.Path("dataset/sample.csv").exists()
        assert not pathlib.Path("config.yaml").exists()


def test_init_then_compare_works(runner, tmp_path):
    """The dataset written by init must be usable by compare verbatim."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        init_result = runner.invoke(cli, ["init"])
        assert init_result.exit_code == 0, init_result.output
        result = runner.invoke(cli, [
            "compare",
            "--baseline", "regex-baseline",
            "--candidate", "regex-enhanced",
            "--dataset", "dataset/sample.csv",
            "--store", str(tmp_path / "test.db"),
        ])
        assert result.exit_code == 0, result.output
        assert "Run ID:" in result.output


def _write_gate(tmp_path, thresholds):
    cfg = tmp_path / "gate.json"
    cfg.write_text(json.dumps({"mode": "strict", "global_thresholds": thresholds}), encoding="utf-8")
    return cfg


def test_compare_json_stdout_only(runner, tmp_path):
    """compare --json prints only a parseable JSON object to stdout."""
    result, _ = _compare(runner, tmp_path, ["--json"])
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)  # stdout must be pure JSON
    for key in ("run_id", "baseline_name", "candidate_name", "dataset_sha",
                "candidate_metrics", "mcnemar_p"):
        assert key in data, key
    assert "strict" in data["candidate_metrics"]
    assert "lenient" in data["candidate_metrics"]
    assert "recall" in data["candidate_metrics"]["strict"]
    # Human text is on stderr, not stdout.
    assert "Run ID:" in result.stderr
    assert "Run ID:" not in result.stdout


def test_gate_json_pass(runner, tmp_path):
    """gate --json on a passing config prints passed=True and exits 0."""
    _compare(runner, tmp_path)
    cfg = _write_gate(tmp_path, {"min_recall": 0.0, "max_fpr": 1.0, "min_f1": 0.0, "max_latency_p99_ms": 100000})
    result = runner.invoke(cli, [
        "gate", "--config", str(cfg), "--run", "latest",
        "--store", str(tmp_path / "test.db"), "--json",
        "--output", str(tmp_path / "ci_summary.md"),
    ])
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["passed"] is True
    assert data["failures"] == []
    assert "run_id" in data


def test_gate_json_fail_structured(runner, tmp_path):
    """gate --json on a failing config exits 1 with structured failures."""
    _compare(runner, tmp_path)
    cfg = _write_gate(tmp_path, {"min_recall": 0.999, "max_fpr": 0.0, "min_f1": 0.999, "max_latency_p99_ms": 100000})
    result = runner.invoke(cli, [
        "gate", "--config", str(cfg), "--run", "latest",
        "--store", str(tmp_path / "test.db"), "--json",
        "--output", str(tmp_path / "ci_summary.md"),
    ])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["passed"] is False
    assert len(data["failures"]) > 0
    for f in data["failures"]:
        assert set(f.keys()) == {"scope", "metric", "value", "threshold"}


def test_gate_summary_md(runner, tmp_path):
    """gate --summary-md writes a baseline/candidate/delta table."""
    _compare(runner, tmp_path)
    cfg = _write_gate(tmp_path, {"min_recall": 0.0, "max_fpr": 1.0, "min_f1": 0.0, "max_latency_p99_ms": 100000})
    summary = tmp_path / "step.md"
    result = runner.invoke(cli, [
        "gate", "--config", str(cfg), "--run", "latest",
        "--store", str(tmp_path / "test.db"), "--summary-md", str(summary),
        "--output", str(tmp_path / "ci_summary.md"),
    ])
    assert result.exit_code == 0, result.output
    text = summary.read_text()
    assert "| Metric | Baseline | Candidate | Delta | Threshold | Status |" in text
    assert "Recall" in text and "Latency p99" in text


def test_compare_summary_md(runner, tmp_path):
    """compare --summary-md writes a table with the threshold column dashed out."""
    summary = tmp_path / "step.md"
    result, _ = _compare(runner, tmp_path, ["--summary-md", str(summary)])
    assert result.exit_code == 0, result.output
    text = summary.read_text()
    assert "| Metric | Baseline | Candidate | Delta | Threshold | Status |" in text


def test_compare_end_to_end(runner, tmp_path):
    """Full compare command should succeed and print a run ID."""
    builtin = (
        pathlib.Path(__file__).parent.parent.parent
        / "guardmeter" / "data" / "builtin" / "sample_10.jsonl"
    )
    db = tmp_path / "test.db"
    result = runner.invoke(cli, [
        "compare",
        "--baseline", "regex",
        "--candidate", "regex",
        "--dataset", str(builtin),
        "--store", str(db),
    ])
    assert result.exit_code == 0, result.output
    assert "Run ID:" in result.output
