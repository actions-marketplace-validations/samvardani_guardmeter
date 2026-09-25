"""Evidence pack: a self-contained, hash-manifested audit bundle for one run.

Bundles the HTML report, an offline dashboard snapshot, the full run JSON (with
guard_info + environment), the gate policy and its result, an informational
control-framework mapping, and a one-page summary — then hashes everything into
MANIFEST.json and zips it. ``guardmeter verify-report`` re-checks the manifest,
so tampering with any file is detectable.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from guardmeter.engine.results import EvalResults
from guardmeter.gate.checker import GateChecker
from guardmeter.gate.config import load_gate_config
from guardmeter.report.generator import ReportGenerator
from guardmeter.report.manifest import write_manifest

_FRAMEWORK_MAPPING = """\
# Control-framework mapping (informational)

This evidence pack supports — but does not by itself satisfy — the following
controls. This is an **informational mapping, not a certification**.

| Framework | Control | How this pack relates |
|---|---|---|
| NIST AI RMF | Measure 2.5 / 2.7 (validity, reliability; security & resilience) | Per-slice recall/FPR, adversarial attack-family results, and the hijack/error accounting evidence the guard was measured, not assumed. |
| NIST AI RMF | Measure 2.11 (fairness across groups) | Metrics sliced by language and category surface uneven performance. |
| ISO/IEC 42001 | §8.4 (operation & performance evaluation) | The run records what was evaluated (guard_info), on what data (dataset sha), under which policy, with a pass/fail gate. |
| ISO/IEC 42001 | §9.1 (monitoring, measurement, analysis) | Reproducible run history with stored metrics and manifests. |
| EU AI Act | Art. 9 (risk management) | Documented residual failure modes: false negatives per family, hijack rate, incomplete-run errors. |
| EU AI Act | Art. 15 (accuracy, robustness, cybersecurity) | Accuracy metrics with confidence intervals; robustness against the agentic attack families; fail-closed behaviour on guard errors. |

Nothing here asserts compliance. Auditors should read the summary, the run
JSON, and the gate result, and confirm the dataset and policy are appropriate
for the system under assessment.
"""


def _summary_md(results: EvalResults, gate_result: Any, gate_path: str | None) -> str:
    strict = results.candidate_metrics.get("strict")
    base = results.baseline_metrics.get("strict")
    gi = results.guard_info or {}
    env = results.environment or {}

    def model(side: str) -> str:
        d = gi.get(side) or {}
        return f" ({d['model']})" if d.get("model") else ""

    lines = [
        "# GuardMeter evidence summary",
        "",
        f"- **Run:** `{results.run_id}`",
        f"- **Date:** {results.timestamp}",
        f"- **Baseline:** {results.baseline_name}{model('baseline')}",
        f"- **Candidate:** {results.candidate_name}{model('candidate')}",
        f"- **Dataset sha:** `{results.dataset_sha}`"
        + (f" · path `{env['dataset_path']}`" if env.get("dataset_path") else ""),
        (f"- **Environment:** GuardMeter {env.get('guardmeter_version', '?')}, "
         f"Python {env.get('python_version', '?')}, policy {env.get('policy', 'strict')}"),
        f"- **Gate:** {'PASS ✅' if gate_result.passed else 'FAIL ❌'}"
        + (f" (policy `{gate_path}`)" if gate_path else ""),
        "",
        "## Headline metrics (candidate, strict)",
        "",
    ]
    if strict:
        evaluated = strict.tp + strict.fp + strict.tn + strict.fn
        recall = f"{strict.recall:.4f}" if evaluated else "n/a"
        f1 = f"{strict.f1:.4f}" if evaluated else "n/a"
        lines += [
            f"- Recall: **{recall}**" + (f" (baseline {base.recall:.4f})" if base and evaluated else ""),
            f"- FPR: **{strict.fpr:.4f}**",
            f"- F1: **{f1}**",
            f"- Latency p99: **{strict.latency_p99:.0f} ms**",
            f"- Hijack rate: **{strict.hijack_rate:.4f}** ({strict.hijacked} samples)",
            f"- Errors: **{strict.error_count}** ({strict.error_rate:.4f}) — excluded from metrics",
        ]
    if not gate_result.passed:
        lines += ["", "## Gate failures", ""]
        lines += [f"- {f}" for f in gate_result.failures]
    return "\n".join(lines) + "\n"


def build_evidence(
    store: Any,
    run_id: str,
    out_dir: str | Path,
    gate_config_path: str | None = None,
    *,
    date: str | None = None,
) -> Path:
    """Write the evidence pack under ``out_dir`` and return the path to the zip.

    ``date`` (YYYY-MM-DD) is used in the zip name; pass it in since the engine
    forbids wall-clock calls — defaults to the run's own timestamp date.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = store.get_run(run_id) if run_id != "latest" else store.latest_run()
    if results is None:
        raise ValueError("no run to build evidence from")

    gate_dict: dict[str, Any] | None = None
    if gate_config_path:
        effective_gate = load_gate_config(gate_config_path)
        gate_dict = effective_gate.model_dump()
    else:
        effective_gate = _default_gate()
    gate_result = GateChecker(effective_gate, store=store).check(results)

    # Artifacts
    ReportGenerator(results, gate_config=gate_dict).build(out_dir / "report.html")

    from guardmeter.serve.snapshot import build_snapshot
    (out_dir / "dashboard.html").write_text(build_snapshot(store), encoding="utf-8")

    (out_dir / "run.json").write_text(json.dumps(results.to_dict(), indent=2), encoding="utf-8")
    (out_dir / "gate-result.json").write_text(json.dumps({
        "passed": gate_result.passed,
        "failures": gate_result.failures,
        "checks": [
            {"scope": c.scope, "metric": c.metric, "value": c.value,
             "threshold": c.threshold, "passed": c.passed} for c in gate_result.checks
        ],
    }, indent=2), encoding="utf-8")
    (out_dir / "gate-policy.json").write_text(
        json.dumps(gate_dict or _default_gate().model_dump(), indent=2), encoding="utf-8")
    (out_dir / "framework-mapping.md").write_text(_FRAMEWORK_MAPPING, encoding="utf-8")
    (out_dir / "summary.md").write_text(
        _summary_md(results, gate_result, gate_config_path), encoding="utf-8")

    # Scenario runs (endpoint-behaviour) are part of the audit story too.
    if hasattr(store, "list_scenario_runs"):
        scenario_runs = store.list_scenario_runs(limit=200)
        if scenario_runs:
            (out_dir / "scenario-runs.json").write_text(
                json.dumps(scenario_runs, indent=2), encoding="utf-8")

    write_manifest(
        out_dir, run_id=results.run_id, dataset_sha=results.dataset_sha,
        git_commit=results.git_commit, include="*",
    )

    day = date or (results.timestamp or "")[:10] or "undated"
    zip_path = out_dir / f"evidence-{results.run_id[:8]}-{day}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out_dir.iterdir()):
            if p.is_file() and p != zip_path:
                zf.write(p, p.name)
    return zip_path


def _default_gate():
    """A permissive gate used when no policy is supplied (records a result anyway)."""
    from guardmeter.gate.schema import GateConfig, GlobalThresholds
    return GateConfig(global_thresholds=GlobalThresholds(
        min_recall=0.0, max_fpr=1.0, min_f1=0.0, max_latency_p99_ms=10_000_000,
        max_hijack_rate=1.0, max_error_rate=1.0))
