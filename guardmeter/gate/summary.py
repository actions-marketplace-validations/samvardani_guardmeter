"""CI gate summary writers: Markdown table and JSON summary."""

from __future__ import annotations

import json
from pathlib import Path

from guardmeter.engine.results import EvalResults
from guardmeter.gate.checker import GateCheckResult
from guardmeter.gate.schema import GateConfig


def write_markdown_summary(
    check_result: GateCheckResult,
    results: EvalResults,
    config: GateConfig,
    output_path: Path,
) -> None:
    """Write a Markdown summary table and a JSON summary alongside it.

    Table columns: Metric | Threshold | Actual | Status
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    policy = config.mode
    cand = results.candidate_metrics.get(policy) or results.candidate_metrics.get("strict")

    lines = ["# GuardMeter CI Gate Summary\n"]
    lines.append(f"**Run:** {results.run_id}  ")
    lines.append(f"**Passed:** {'✅ Yes' if check_result.passed else '❌ No'}  \n")

    thr = config.global_thresholds
    lines.append("| Metric | Threshold | Actual | Status |")
    lines.append("|--------|-----------|--------|--------|")

    if cand:
        rows = [
            ("Recall", f"≥ {thr.min_recall}", f"{cand.recall:.4f}",
             "✅" if cand.recall >= thr.min_recall else "❌"),
            ("FPR", f"≤ {thr.max_fpr}", f"{cand.fpr:.4f}",
             "✅" if cand.fpr <= thr.max_fpr else "❌"),
            ("F1", f"≥ {thr.min_f1}", f"{cand.f1:.4f}",
             "✅" if cand.f1 >= thr.min_f1 else "❌"),
            ("Latency p99", f"≤ {thr.max_latency_p99_ms} ms", f"{cand.latency_p99:.1f} ms",
             "✅" if cand.latency_p99 <= thr.max_latency_p99_ms else "❌"),
        ]
        for metric, threshold, actual, status in rows:
            lines.append(f"| {metric} | {threshold} | {actual} | {status} |")

    if check_result.failures:
        lines.append("\n## Failures\n")
        for f in check_result.failures:
            lines.append(f"- ❌ {f}")

    if check_result.warnings:
        lines.append("\n## Warnings\n")
        for w in check_result.warnings:
            lines.append(f"- ⚠️ {w}")

    output_path.write_text("\n".join(lines), encoding="utf-8")

    # Write companion JSON
    json_path = output_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "run_id": results.run_id,
                "passed": check_result.passed,
                "failures": check_result.failures,
                "warnings": check_result.warnings,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
