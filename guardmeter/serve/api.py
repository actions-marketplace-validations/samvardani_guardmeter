"""Server-side helpers for the GuardMeter app API (pure, testable functions)."""

from __future__ import annotations

import csv
import io
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from guardmeter.engine.results import EvalResults
from guardmeter.gate.checker import GateChecker
from guardmeter.gate.config import load_gate_config, parse_gate_config
from guardmeter.gate.schema import GateConfig

GATE_PATH = Path("gate.json")
DATASET_DIR = Path("dataset")


def current_gate_config() -> GateConfig | None:
    """Load ./gate.json if present, else None (so gate_pass is null with no policy)."""
    if not GATE_PATH.exists():
        return None
    try:
        return load_gate_config(GATE_PATH)
    except (ValueError, OSError):
        return None


def gate_pass_for(results: EvalResults, gate_config: GateConfig | None) -> bool | None:
    """True/False if a gate policy exists, else None."""
    if gate_config is None:
        return None
    return GateChecker(gate_config).check(results).passed


def runs_payload(store: Any, limit: int = 100, guard: str = "", dataset: str = "", q: str = "") -> list[dict[str, Any]]:
    """Return run summaries filtered by guard/dataset/q, each with gate_pass."""
    gate_config = current_gate_config()
    out: list[dict[str, Any]] = []
    for summary in store.list_runs(limit=limit):
        if guard and guard not in (summary.get("baseline"), summary.get("candidate")):
            continue
        if dataset and dataset != (summary.get("dataset_sha") or ""):
            continue
        if q:
            hay = " ".join(str(summary.get(k) or "") for k in
                           ("run_id", "tag", "baseline", "candidate", "note")).lower()
            if q.lower() not in hay:
                continue
        gate_pass: bool | None = None
        if gate_config is not None:
            try:
                gate_pass = gate_pass_for(store.get_run(summary["run_id"]), gate_config)
            except KeyError:
                gate_pass = None
        summary["gate_pass"] = gate_pass
        out.append(summary)
    return out


def _is_positive(label: str) -> bool:
    return label != "benign"


def samples_payload(results: EvalResults, filt: str = "all", q: str = "",
                    offset: int = 0, limit: int = 100) -> dict[str, Any]:
    """Filter/paginate a run's per-sample results."""
    rows = []
    for s in results.sample_results:
        if filt == "fn" and not (_is_positive(s.label) and s.candidate_pred == "pass"):
            continue
        if filt == "fp" and not (s.label == "benign" and s.candidate_pred == "flag"):
            continue
        if filt == "mismatch" and s.baseline_pred == s.candidate_pred:
            continue
        if filt == "disagree" and s.judge_verdict != "disagree":
            continue
        if q:
            hay = " ".join(str(v or "") for v in
                           (s.text, s.category, s.language, s.attack_type,
                            s.baseline_pred, s.candidate_pred, s.label)).lower()
            if q.lower() not in hay:
                continue
        rows.append({
            "text": s.text, "label": s.label, "category": s.category,
            "language": s.language, "attack_type": s.attack_type,
            "baseline_pred": s.baseline_pred, "candidate_pred": s.candidate_pred,
            "baseline_score": s.baseline_score, "candidate_score": s.candidate_score,
            "baseline_latency_ms": s.baseline_latency_ms,
            "candidate_latency_ms": s.candidate_latency_ms,
            "judge_verdict": s.judge_verdict,
        })
    total = len(rows)
    return {"total": total, "offset": offset, "limit": limit, "rows": rows[offset:offset + limit]}


def run_csv(results: EvalResults) -> str:
    """Serialise a run's per-sample results to CSV text."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["text", "label", "category", "language", "attack_type",
                     "baseline_pred", "candidate_pred", "baseline_score",
                     "candidate_score", "baseline_latency_ms", "candidate_latency_ms"])
    for s in results.sample_results:
        writer.writerow([s.text, s.label, s.category, s.language, s.attack_type or "",
                         s.baseline_pred, s.candidate_pred, s.baseline_score,
                         s.candidate_score, s.baseline_latency_ms, s.candidate_latency_ms])
    return buf.getvalue()


def gate_evaluate(gate_dict: dict[str, Any], results: EvalResults) -> dict[str, Any]:
    """Dry-run a gate config against a run; same shape as `gate --json`."""
    config = parse_gate_config(gate_dict)
    result = GateChecker(config).check(results)
    return {
        "passed": result.passed,
        "failures": [f.to_dict() for f in result.structured_failures],
        "run_id": results.run_id,
    }


def write_gate(gate_dict: dict[str, Any]) -> None:
    """Validate then write gate.json, backing up any existing file to gate.json.bak."""
    parse_gate_config(gate_dict)  # validate before touching disk
    import json
    if GATE_PATH.exists():
        shutil.copy2(GATE_PATH, GATE_PATH.with_suffix(".json.bak"))
    GATE_PATH.write_text(json.dumps(gate_dict, indent=2), encoding="utf-8")


# ── datasets ────────────────────────────────────────────────────────────────

def _dataset_path(name: str) -> Path | None:
    if "/" in name or "\\" in name or ".." in name:
        return None
    p = DATASET_DIR / name
    return p if p.is_file() else None


def datasets_list() -> list[dict[str, Any]]:
    """List dataset files under ./dataset with row counts."""
    if not DATASET_DIR.is_dir():
        return []
    from guardmeter.data.loader import load_dataset
    out = []
    for p in sorted(DATASET_DIR.glob("*.csv")) + sorted(DATASET_DIR.glob("*.jsonl")):
        try:
            rows = len(load_dataset(str(p)))
        except Exception:  # noqa: BLE001 (a malformed dataset shouldn't break the listing)
            rows = 0
        out.append({"name": p.name, "rows": rows})
    return out


def dataset_stats(name: str) -> dict[str, Any] | None:
    """Label/category/language/attack_type counts for one dataset."""
    p = _dataset_path(name)
    if p is None:
        return None
    from guardmeter.data.loader import load_dataset
    recs = load_dataset(str(p))
    return {
        "name": name,
        "total": len(recs),
        "labels": dict(Counter(r.label for r in recs)),
        "categories": dict(Counter(r.category for r in recs)),
        "languages": dict(Counter(r.language for r in recs)),
        "attack_types": dict(Counter(r.attack_type or "none" for r in recs)),
    }


def dataset_rows(name: str, q: str = "", offset: int = 0, limit: int = 100) -> dict[str, Any] | None:
    """Paginated rows of one dataset, optionally filtered by q."""
    p = _dataset_path(name)
    if p is None:
        return None
    from guardmeter.data.loader import load_dataset
    recs = load_dataset(str(p))
    rows = [r.model_dump() for r in recs]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in " ".join(str(v or "") for v in r.values()).lower()]
    return {"total": len(rows), "offset": offset, "limit": limit, "rows": rows[offset:offset + limit]}
