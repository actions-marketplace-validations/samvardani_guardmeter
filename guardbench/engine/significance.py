"""Statistical significance tests for comparing two guards."""

from __future__ import annotations

from guardbench.core.guard import GuardResult
from guardbench.data.schema import DatasetRecord


def mcnemar_test(
    preds_a: list[GuardResult],
    preds_b: list[GuardResult],
    records: list[DatasetRecord],
    policy: str = "strict",
) -> tuple[float, float]:
    """Compute McNemar's test statistic and p-value comparing two guard predictions.

    Returns (statistic, p_value). p_value < 0.05 indicates statistical significance.
    Uses the continuity-corrected version when possible.
    """
    from scipy.stats import chi2  # type: ignore[import-untyped]

    # Count discordant pairs
    b = 0  # A correct, B wrong
    c = 0  # A wrong, B correct
    for pa, pb, rec in zip(preds_a, preds_b, records):
        label = rec.label
        gt_pos = (label != "benign") if policy == "strict" else (label == "unsafe")
        a_correct = (pa.prediction == "flag") == gt_pos
        b_correct = (pb.prediction == "flag") == gt_pos
        if a_correct and not b_correct:
            b += 1
        elif not a_correct and b_correct:
            c += 1

    n = b + c
    if n == 0:
        return 0.0, 1.0

    # McNemar's with continuity correction
    statistic = (abs(b - c) - 1.0) ** 2 / n
    p_value = float(1.0 - chi2.cdf(statistic, df=1))
    return round(statistic, 4), round(p_value, 4)
