"""Chart data builders for the HTML report."""

from __future__ import annotations

from typing import Any

from guardmeter.engine.results import EvalResults


def threshold_sweep_data(results: EvalResults) -> dict[str, Any]:
    """Build Chart.js data for a threshold sweep of the candidate guard's real scores.

    Sweeps decision thresholds from 0.0 to 1.0 (step 0.05) over the per-sample
    ``candidate_score`` values: a sample is flagged when ``score >= threshold``.
    Ground truth uses the strict policy (any non-benign label is positive).

    Returns a dict with keys ``thresholds``, ``precision``, ``recall``, ``fpr``,
    or ``{}`` when no candidate scores are available (e.g. runs stored before
    scores were persisted) — the template hides the chart in that case.
    """
    samples = results.sample_results
    if not samples:
        return {}

    scored = [s for s in samples if s.candidate_score is not None]
    if not scored:
        return {}

    thresholds = [round(i * 0.05, 2) for i in range(21)]  # 0.00 .. 1.00
    precisions: list[float] = []
    recalls: list[float] = []
    fprs: list[float] = []

    for thr in thresholds:
        tp = fp = tn = fn = 0
        for s in scored:
            score = s.candidate_score
            if score is None:
                continue
            gt_pos = s.label != "benign"
            pr_pos = score >= thr
            if gt_pos and pr_pos:
                tp += 1
            elif not gt_pos and pr_pos:
                fp += 1
            elif not gt_pos and not pr_pos:
                tn += 1
            else:
                fn += 1
        precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
        fpr = round(fp / (fp + tn), 3) if (fp + tn) > 0 else 0.0
        precisions.append(precision)
        recalls.append(recall)
        fprs.append(fpr)

    return {"thresholds": thresholds, "precision": precisions, "recall": recalls, "fpr": fprs}
