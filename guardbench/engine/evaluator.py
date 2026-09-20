"""Evaluator: orchestrates guard predictions, metrics, slices, and significance tests."""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from guardbench.core.guard import Guard
from guardbench.core.io_utils import git_commit_sha, hash_content, new_run_id
from guardbench.data.schema import DatasetRecord
from guardbench.engine.metrics import compute_metrics, compute_slices
from guardbench.engine.results import EvalResults, SampleResult
from guardbench.engine.significance import mcnemar_test

logger = logging.getLogger(__name__)


@dataclass
class EvalConfig:
    """Configuration for an evaluation run."""

    policy: str = "strict"
    slices: List[str] = field(default_factory=lambda: ["category", "language"])
    run_id: Optional[str] = None  # auto-generated UUID if None
    include_lenient: bool = True  # also compute lenient-policy metrics


class Evaluator:
    """Orchestrates a full evaluation: both guards × both policies × per-slice metrics."""

    def __init__(
        self,
        baseline: Guard,
        candidate: Guard,
        dataset: List[DatasetRecord],
        config: EvalConfig | None = None,
        judge: Any = None,
    ) -> None:
        """Initialise with two guards, a dataset, optional config, and optional judge."""
        self.baseline = baseline
        self.candidate = candidate
        self.dataset = dataset
        self.config = config or EvalConfig()
        self.judge = judge

    def run(self) -> EvalResults:
        """Run the full evaluation and return EvalResults."""
        run_id = self.config.run_id or new_run_id()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        git_commit = git_commit_sha()

        # Hash the dataset for reproducibility
        serialised = json.dumps(
            [r.model_dump() for r in self.dataset], sort_keys=True
        ).encode("utf-8")
        dataset_sha = hash_content(serialised)

        texts = [r.text for r in self.dataset]

        logger.info("Running baseline (%s) on %d samples", self.baseline.name, len(texts))
        base_preds = self.baseline.batch_predict(
            texts,
            **{},  # metadata passed per-record below if needed
        )

        logger.info("Running candidate (%s) on %d samples", self.candidate.name, len(texts))
        cand_preds = self.candidate.batch_predict(texts)

        # Compute metrics for both policies
        policies = ["strict"]
        if self.config.include_lenient:
            policies.append("lenient")

        base_metrics = {}
        cand_metrics = {}
        base_slices = {}
        cand_slices = {}

        for pol in policies:
            base_conf = _confusion(base_preds, self.dataset, pol)
            cand_conf = _confusion(cand_preds, self.dataset, pol)
            base_lats = [p.latency_ms for p in base_preds]
            cand_lats = [p.latency_ms for p in cand_preds]

            base_metrics[pol] = compute_metrics(base_conf, base_lats)
            cand_metrics[pol] = compute_metrics(cand_conf, cand_lats)
            base_slices[pol] = compute_slices(base_preds, self.dataset, pol, self.config.slices)
            cand_slices[pol] = compute_slices(cand_preds, self.dataset, pol, self.config.slices)

        # McNemar significance test on primary policy
        try:
            from scipy import stats as _  # noqa: F401
            _, mcnemar_p = mcnemar_test(base_preds, cand_preds, self.dataset, policy=self.config.policy)
        except ImportError:
            logger.warning("scipy not available; skipping McNemar test")
            mcnemar_p = None

        # Build per-sample results
        sample_results = []
        for pred_b, pred_c, rec in zip(base_preds, cand_preds, self.dataset):
            sample_results.append(
                SampleResult(
                    text=rec.text,
                    label=rec.label,
                    category=rec.category,
                    language=rec.language,
                    baseline_pred=pred_b.prediction,
                    candidate_pred=pred_c.prediction,
                )
            )

        # LLM-as-judge (optional)
        judge_agreement_rate = None
        if self.judge is not None:
            logger.info("Running judge on %d samples", len(texts))
            verdicts = []
            for pred_c, rec in zip(cand_preds, self.dataset):
                try:
                    verdict = self.judge.evaluate(rec.text, pred_c)
                    verdicts.append(verdict.agrees)
                    sample_results[len(verdicts) - 1].judge_verdict = (
                        "agree" if verdict.agrees else "disagree"
                    )
                except Exception as exc:
                    logger.warning("Judge failed on sample: %s", exc)
                    verdicts.append(None)
            valid = [v for v in verdicts if v is not None]
            if valid:
                judge_agreement_rate = round(sum(1 for v in valid if v) / len(valid), 4)

        return EvalResults(
            run_id=run_id,
            dataset_sha=dataset_sha,
            git_commit=git_commit,
            timestamp=timestamp,
            baseline_name=self.baseline.name,
            candidate_name=self.candidate.name,
            baseline_metrics=base_metrics,
            candidate_metrics=cand_metrics,
            baseline_slices=base_slices,
            candidate_slices=cand_slices,
            sample_results=sample_results,
            mcnemar_p=mcnemar_p,
            judge_agreement_rate=judge_agreement_rate,
        )


def _confusion(preds, records, policy):
    """Compute confusion dict for a policy."""
    tp = fp = tn = fn = 0
    for pred, rec in zip(preds, records):
        gt_pos = (rec.label != "benign") if policy == "strict" else (rec.label == "unsafe")
        pr_pos = pred.prediction == "flag"
        if gt_pos and pr_pos:
            tp += 1
        elif not gt_pos and pr_pos:
            fp += 1
        elif not gt_pos and not pr_pos:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}
