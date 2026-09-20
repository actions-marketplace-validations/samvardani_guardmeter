"""Tests for the report generator."""

from __future__ import annotations

import json
import re

from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.report.generator import ReportGenerator


def test_report_build_creates_file(sample_records, regex_enhanced, tmp_path):
    """ReportGenerator.build() should create a file at the given path."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    out = tmp_path / "report" / "index.html"
    generator = ReportGenerator(results)
    returned_path = generator.build(out)
    assert out.exists()
    assert returned_path == out


def test_report_is_valid_html(sample_records, regex_enhanced, tmp_path):
    """The generated report should be a valid HTML document."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    out = tmp_path / "index.html"
    ReportGenerator(results).build(out)
    content = out.read_text(encoding="utf-8")
    assert "<html" in content.lower()
    assert "</html>" in content.lower()


def test_report_contains_run_id(sample_records, regex_enhanced, tmp_path):
    """Report should contain the run ID."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    out = tmp_path / "index.html"
    ReportGenerator(results).build(out)
    content = out.read_text(encoding="utf-8")
    assert results.run_id in content


def test_report_compliance_section_present(sample_records, regex_enhanced, tmp_path):
    """Report should contain the compliance reference section."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    out = tmp_path / "index.html"
    ReportGenerator(results).build(out)
    content = out.read_text(encoding="utf-8")
    assert "compliance" in content.lower()
    assert "EU AI Act" in content


def test_report_latency_arrays_match_sample_count(sample_records, regex_enhanced, tmp_path):
    """The per-sample latency arrays embedded in the report must have one value per sample."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    n = len(results.sample_results)
    out = tmp_path / "index.html"
    ReportGenerator(results).build(out)
    content = out.read_text(encoding="utf-8")
    base = json.loads(re.search(r"const baseLatencies = (\[.*?\]);", content).group(1))
    cand = json.loads(re.search(r"const candLatencies = (\[.*?\]);", content).group(1))
    assert len(base) == n
    assert len(cand) == n


def test_report_escapes_xss_in_candidate_name(sample_records, regex_enhanced, tmp_path):
    """A malicious guard name must be HTML-escaped, not rendered as live markup."""
    payload = "<img src=x onerror=alert(1)>"
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    results.candidate_name = payload
    out = tmp_path / "index.html"
    ReportGenerator(results).build(out)
    content = out.read_text(encoding="utf-8")
    assert "&lt;img" in content
    assert "<img" not in content


def test_report_auto_names_output(sample_records, regex_enhanced, tmp_path):
    """When output_path is None, report is written to report/index.html."""
    import os
    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
        results = ev.run()
        out = ReportGenerator(results).build()
        assert out.exists()
    finally:
        os.chdir(orig)
