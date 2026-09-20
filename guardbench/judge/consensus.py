"""Consensus analysis: agreement rate and disagreement categorization."""

from __future__ import annotations

from typing import Any

from guardbench.engine.results import EvalResults
from guardbench.judge.base import JudgeVerdict


def agreement_rate(verdicts: list[JudgeVerdict]) -> float:
    """Return the fraction of verdicts where the judge agreed with the guard.

    Returns 0.0 for an empty list.
    """
    if not verdicts:
        return 0.0
    return round(sum(1 for v in verdicts if v.agrees) / len(verdicts), 4)


def disagreement_analysis(
    results: EvalResults,
    verdicts: list[JudgeVerdict],
) -> dict[str, list[dict[str, Any]]]:
    """Categorise disagreements into false positive and false negative candidates.

    Returns:
        {
            "fp_candidates": [...],  # guard flagged, judge disagrees
            "fn_candidates": [...],  # guard passed, judge disagrees
        }
    """
    fp_candidates = []
    fn_candidates = []

    samples = results.sample_results
    if len(samples) != len(verdicts):
        raise ValueError(
            f"Mismatch: {len(samples)} sample results vs {len(verdicts)} verdicts"
        )

    for sample, verdict in zip(samples, verdicts):
        if verdict.agrees:
            continue
        entry = {
            "text": sample.text,
            "label": sample.label,
            "category": sample.category,
            "language": sample.language,
            "candidate_pred": sample.candidate_pred,
            "judge_suggested": verdict.suggested_label,
            "judge_reasoning": verdict.reasoning,
            "judge_confidence": verdict.confidence,
        }
        if sample.candidate_pred == "flag":
            fp_candidates.append(entry)
        else:
            fn_candidates.append(entry)

    return {"fp_candidates": fp_candidates, "fn_candidates": fn_candidates}
