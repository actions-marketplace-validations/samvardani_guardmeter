"""JSON-file-backed run store: one JSON file per run."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from guardbench.engine.results import EvalResults
from guardbench.store.base import RunStore

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path.home() / ".guardbench" / "runs"


class JSONFileStore(RunStore):
    """Stores evaluation runs as individual JSON files in a directory."""

    def __init__(self, dir_path: Path | str | None = None) -> None:
        """Initialise with an optional directory path; defaults to ~/.guardbench/runs/."""
        self.dir_path = Path(dir_path) if dir_path else _DEFAULT_DIR
        self.dir_path.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.dir_path / f"{run_id}.json"

    def save_run(self, results: EvalResults) -> None:
        """Write an EvalResults to a JSON file."""
        p = self._path(results.run_id)
        p.write_text(json.dumps(results.to_dict(), indent=2), encoding="utf-8")
        logger.debug("Saved run %s to %s", results.run_id, p)

    def get_run(self, run_id: str) -> EvalResults:
        """Load an EvalResults from a JSON file. Raises KeyError if not found."""
        p = self._path(run_id)
        if not p.exists():
            raise KeyError(f"Run '{run_id}' not found in store (looked for {p})")
        return EvalResults.from_dict(json.loads(p.read_text(encoding="utf-8")))

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return summary dicts for the most recent runs, sorted by timestamp descending."""
        files = sorted(self.dir_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        summaries = []
        for p in files[:limit]:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                cand_strict = d.get("candidate_metrics", {}).get("strict", {})
                summaries.append(
                    {
                        "run_id": d.get("run_id"),
                        "timestamp": d.get("timestamp"),
                        "baseline": d.get("baseline_name"),
                        "candidate": d.get("candidate_name"),
                        "recall": cand_strict.get("recall"),
                        "fpr": cand_strict.get("fpr"),
                    }
                )
            except Exception as exc:  # noqa: BLE001 (intentional resilience boundary)
                logger.warning("Failed to parse run file %s: %s", p, exc)
        return summaries

    def latest_run(self) -> EvalResults | None:
        """Return the most recently saved EvalResults, or None if the store is empty."""
        files = sorted(self.dir_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        return EvalResults.from_dict(json.loads(files[0].read_text(encoding="utf-8")))

    def compare_runs(self, run_id_a: str, run_id_b: str) -> dict[str, Any]:
        """Return a delta dict comparing two runs' candidate metrics."""
        a = self.get_run(run_id_a)
        b = self.get_run(run_id_b)
        a_m = a.candidate_metrics.get("strict")
        b_m = b.candidate_metrics.get("strict")
        if a_m is None or b_m is None:
            return {"error": "Missing strict metrics for one or both runs"}
        return {
            "run_a": run_id_a,
            "run_b": run_id_b,
            "recall_delta": round(b_m.recall - a_m.recall, 4),
            "fpr_delta": round(b_m.fpr - a_m.fpr, 4),
            "f1_delta": round(b_m.f1 - a_m.f1, 4),
            "precision_delta": round(b_m.precision - a_m.precision, 4),
        }
