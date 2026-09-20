"""EvalResults dataclass: the canonical output of a full evaluation run."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from guardmeter.engine.metrics import MetricsBundle

# policy → (dimension values, ...) → metrics
SliceFamily = dict[str, dict[tuple[Any, ...], MetricsBundle]]


@dataclass
class SampleResult:
    """Per-sample result: both guard predictions, scores, latencies, and optional judge verdict."""

    text: str
    label: str
    category: str
    language: str
    baseline_pred: str  # "pass" | "flag"
    candidate_pred: str  # "pass" | "flag"
    judge_verdict: str | None = None  # "agree" | "disagree" | None
    baseline_score: float | None = None
    candidate_score: float | None = None
    baseline_latency_ms: float = 0.0
    candidate_latency_ms: float = 0.0
    attack_type: str | None = None


def _bundle_to_dict(b: MetricsBundle) -> dict[str, Any]:
    return {
        "tp": b.tp, "fp": b.fp, "tn": b.tn, "fn": b.fn,
        "precision": b.precision, "recall": b.recall, "f1": b.f1,
        "fpr": b.fpr, "fnr": b.fnr,
        "recall_lo": b.recall_lo, "recall_hi": b.recall_hi,
        "fpr_lo": b.fpr_lo, "fpr_hi": b.fpr_hi,
        "latency_p50": b.latency_p50, "latency_p90": b.latency_p90,
        "latency_p95": b.latency_p95, "latency_p99": b.latency_p99,
        "latency_mean": b.latency_mean, "latency_max": b.latency_max,
    }


def _bundle_from_dict(d: dict[str, Any]) -> MetricsBundle:
    return MetricsBundle(**{k: d[k] for k in MetricsBundle.__dataclass_fields__ if k in d})


@dataclass
class EvalResults:
    """Complete results from a single evaluation run."""

    run_id: str
    dataset_sha: str
    git_commit: str
    timestamp: str  # ISO 8601
    baseline_name: str
    candidate_name: str
    # Metrics keyed by policy: {"strict": MetricsBundle, "lenient": MetricsBundle}
    baseline_metrics: dict[str, MetricsBundle] = field(default_factory=dict)
    candidate_metrics: dict[str, MetricsBundle] = field(default_factory=dict)
    # Slices keyed by policy → (category, language) → MetricsBundle
    baseline_slices: SliceFamily = field(default_factory=dict)
    candidate_slices: SliceFamily = field(default_factory=dict)
    # Parallel attack-type family, keyed by policy → (attack_type,) → MetricsBundle
    baseline_attack_slices: SliceFamily = field(default_factory=dict)
    candidate_attack_slices: SliceFamily = field(default_factory=dict)
    sample_results: list[SampleResult] = field(default_factory=list)
    mcnemar_p: float | None = None
    judge_agreement_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        def slices_to_dict(slices: SliceFamily) -> dict[str, dict[str, Any]]:
            out: dict[str, dict[str, Any]] = {}
            for policy, per_slice in slices.items():
                out[policy] = {
                    json.dumps(list(k)): _bundle_to_dict(v)
                    for k, v in per_slice.items()
                }
            return out

        return {
            "run_id": self.run_id,
            "dataset_sha": self.dataset_sha,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "baseline_name": self.baseline_name,
            "candidate_name": self.candidate_name,
            "baseline_metrics": {k: _bundle_to_dict(v) for k, v in self.baseline_metrics.items()},
            "candidate_metrics": {k: _bundle_to_dict(v) for k, v in self.candidate_metrics.items()},
            "baseline_slices": slices_to_dict(self.baseline_slices),
            "candidate_slices": slices_to_dict(self.candidate_slices),
            "baseline_attack_slices": slices_to_dict(self.baseline_attack_slices),
            "candidate_attack_slices": slices_to_dict(self.candidate_attack_slices),
            "sample_results": [
                {"text": s.text, "label": s.label, "category": s.category,
                 "language": s.language, "baseline_pred": s.baseline_pred,
                 "candidate_pred": s.candidate_pred, "judge_verdict": s.judge_verdict,
                 "baseline_score": s.baseline_score, "candidate_score": s.candidate_score,
                 "baseline_latency_ms": s.baseline_latency_ms,
                 "candidate_latency_ms": s.candidate_latency_ms,
                 "attack_type": s.attack_type}
                for s in self.sample_results
            ],
            "mcnemar_p": self.mcnemar_p,
            "judge_agreement_rate": self.judge_agreement_rate,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvalResults:
        """Deserialise from a dict (as produced by to_dict)."""
        def slices_from_dict(raw: dict[str, dict[str, Any]]) -> SliceFamily:
            out: SliceFamily = {}
            for policy, per_slice in raw.items():
                out[policy] = {}
                for k_str, v in per_slice.items():
                    key = tuple(json.loads(k_str))
                    out[policy][key] = _bundle_from_dict(v)
            return out

        obj = cls(
            run_id=d["run_id"],
            dataset_sha=d["dataset_sha"],
            git_commit=d["git_commit"],
            timestamp=d["timestamp"],
            baseline_name=d["baseline_name"],
            candidate_name=d["candidate_name"],
        )
        obj.baseline_metrics = {k: _bundle_from_dict(v) for k, v in d.get("baseline_metrics", {}).items()}
        obj.candidate_metrics = {k: _bundle_from_dict(v) for k, v in d.get("candidate_metrics", {}).items()}
        obj.baseline_slices = slices_from_dict(d.get("baseline_slices", {}))
        obj.candidate_slices = slices_from_dict(d.get("candidate_slices", {}))
        obj.baseline_attack_slices = slices_from_dict(d.get("baseline_attack_slices", {}))
        obj.candidate_attack_slices = slices_from_dict(d.get("candidate_attack_slices", {}))
        obj.sample_results = [
            SampleResult(
                text=s["text"], label=s["label"], category=s["category"],
                language=s["language"], baseline_pred=s["baseline_pred"],
                candidate_pred=s["candidate_pred"], judge_verdict=s.get("judge_verdict"),
                baseline_score=s.get("baseline_score"),
                candidate_score=s.get("candidate_score"),
                baseline_latency_ms=s.get("baseline_latency_ms", 0.0),
                candidate_latency_ms=s.get("candidate_latency_ms", 0.0),
                attack_type=s.get("attack_type"),
            )
            for s in d.get("sample_results", [])
        ]
        obj.mcnemar_p = d.get("mcnemar_p")
        obj.judge_agreement_rate = d.get("judge_agreement_rate")
        return obj
