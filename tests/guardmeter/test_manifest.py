"""Tests for the report integrity manifest and verify-report."""

from __future__ import annotations

from click.testing import CliRunner

from guardmeter.cli.main import cli
from guardmeter.report.generator import ReportGenerator
from guardmeter.report.manifest import MANIFEST_NAME, verify_manifest, write_manifest


def _build_report(records, guard, tmp_path):
    from guardmeter.engine.evaluator import EvalConfig, Evaluator
    results = Evaluator(guard, guard, records, EvalConfig()).run()
    out = tmp_path / "report" / "index.html"
    ReportGenerator(results).build(out)
    return results, out.parent


def test_manifest_written_and_verifies(sample_records, regex_enhanced, tmp_path):
    results, report_dir = _build_report(sample_records, regex_enhanced, tmp_path)
    write_manifest(report_dir, run_id=results.run_id, dataset_sha=results.dataset_sha)
    assert (report_dir / MANIFEST_NAME).exists()
    ok, problems = verify_manifest(report_dir)
    assert ok, problems


def test_tampered_file_fails_verification(sample_records, regex_enhanced, tmp_path):
    _, report_dir = _build_report(sample_records, regex_enhanced, tmp_path)
    write_manifest(report_dir)
    (report_dir / "index.html").write_text("<html>tampered</html>", encoding="utf-8")
    ok, problems = verify_manifest(report_dir)
    assert not ok
    assert any("index.html" in p for p in problems)


def test_verify_report_cli_exit_codes(sample_records, regex_enhanced, tmp_path):
    _, report_dir = _build_report(sample_records, regex_enhanced, tmp_path)
    write_manifest(report_dir)
    runner = CliRunner()

    ok = runner.invoke(cli, ["verify-report", str(report_dir)])
    assert ok.exit_code == 0, ok.output

    (report_dir / "index.html").write_text("tampered", encoding="utf-8")
    bad = runner.invoke(cli, ["verify-report", str(report_dir)])
    assert bad.exit_code == 1
    assert "FAILED" in bad.output


def test_verify_report_missing_manifest(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["verify-report", str(tmp_path)])
    assert result.exit_code == 1
