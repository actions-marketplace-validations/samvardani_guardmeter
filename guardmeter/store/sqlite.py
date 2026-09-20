"""SQLite-backed run store."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from guardmeter.engine.results import EvalResults
from guardmeter.store.base import RunStore

logger = logging.getLogger(__name__)


def _default_db() -> Path:
    return Path.home() / ".guardmeter" / "history.db"


def _legacy_db() -> Path:
    return Path.home() / ".guardbench" / "history.db"


class SQLiteStore(RunStore):
    """Stores evaluation runs in a local SQLite database."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise with an optional DB path; defaults to ~/.guardmeter/history.db."""
        self.db_path = Path(db_path) if db_path else _default_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path is None:
            self._migrate_legacy_db()
        self._init_db()

    def _migrate_legacy_db(self) -> None:
        """One-time migration: copy the old ~/.guardbench history into ~/.guardmeter."""
        legacy = _legacy_db()
        if not self.db_path.exists() and legacy.exists():
            shutil.copy2(legacy, self.db_path)
            logger.info("Migrated run history from %s to %s", legacy, self.db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id     TEXT PRIMARY KEY,
                    timestamp  TEXT NOT NULL,
                    dataset_sha TEXT,
                    git_commit  TEXT,
                    baseline    TEXT,
                    candidate   TEXT,
                    metrics_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sample_results (
                    run_id   TEXT,
                    row_idx  INTEGER,
                    text     TEXT,
                    label    TEXT,
                    category TEXT,
                    language TEXT,
                    baseline_pred TEXT,
                    candidate_pred TEXT,
                    baseline_score REAL,
                    candidate_score REAL,
                    baseline_latency_ms REAL,
                    candidate_latency_ms REAL
                )
            """)
            # Migrate existing databases created before the score/latency columns.
            existing = {row[1] for row in conn.execute("PRAGMA table_info(sample_results)")}
            for col in (
                "baseline_score", "candidate_score",
                "baseline_latency_ms", "candidate_latency_ms",
            ):
                if col not in existing:
                    conn.execute(f"ALTER TABLE sample_results ADD COLUMN {col} REAL")
            if "attack_type" not in existing:
                conn.execute("ALTER TABLE sample_results ADD COLUMN attack_type TEXT")
            # Migrate runs table for user tag/note metadata.
            run_cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
            for col in ("tag", "note"):
                if col not in run_cols:
                    conn.execute(f"ALTER TABLE runs ADD COLUMN {col} TEXT")
            conn.commit()

    _RUN_COLS = "run_id, timestamp, dataset_sha, git_commit, baseline, candidate, metrics_json"

    def save_run(self, results: EvalResults) -> None:
        """Persist an EvalResults to the SQLite store."""
        data = results.to_dict()
        metrics_json = json.dumps(
            {
                "baseline_metrics": data["baseline_metrics"],
                "candidate_metrics": data["candidate_metrics"],
                "baseline_slices": data["baseline_slices"],
                "candidate_slices": data["candidate_slices"],
                "baseline_attack_slices": data["baseline_attack_slices"],
                "candidate_attack_slices": data["candidate_attack_slices"],
                "mcnemar_p": data["mcnemar_p"],
                "judge_agreement_rate": data["judge_agreement_rate"],
            }
        )
        with closing(self._connect()) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO runs ({self._RUN_COLS}) VALUES (?,?,?,?,?,?,?)",
                (
                    results.run_id,
                    results.timestamp,
                    results.dataset_sha,
                    results.git_commit,
                    results.baseline_name,
                    results.candidate_name,
                    metrics_json,
                ),
            )
            conn.executemany(
                "INSERT INTO sample_results (run_id, row_idx, text, label, category, language, "
                "baseline_pred, candidate_pred, baseline_score, candidate_score, "
                "baseline_latency_ms, candidate_latency_ms, attack_type) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        results.run_id, i,
                        s.text, s.label, s.category, s.language,
                        s.baseline_pred, s.candidate_pred,
                        s.baseline_score, s.candidate_score,
                        s.baseline_latency_ms, s.candidate_latency_ms,
                        s.attack_type,
                    )
                    for i, s in enumerate(results.sample_results)
                ],
            )
            conn.commit()
        logger.debug("Saved run %s to SQLite", results.run_id)

    def get_run(self, run_id: str) -> EvalResults:
        """Retrieve an EvalResults by run_id. Raises KeyError if not found."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT {self._RUN_COLS} FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Run '{run_id}' not found in store")
        return self._row_to_results(row)

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return summary dicts for the most recent runs, newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT run_id, timestamp, dataset_sha, baseline, candidate, tag, note, metrics_json "
                "FROM runs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        summaries = []
        for run_id, ts, dataset_sha, baseline, candidate, tag, note, metrics_json in rows:
            metrics = json.loads(metrics_json) if metrics_json else {}
            cand_strict = (metrics.get("candidate_metrics") or {}).get("strict", {})
            summaries.append(
                {
                    "run_id": run_id,
                    "timestamp": ts,
                    "dataset_sha": dataset_sha,
                    "baseline": baseline,
                    "candidate": candidate,
                    "tag": tag,
                    "note": note,
                    "recall": cand_strict.get("recall"),
                    "fpr": cand_strict.get("fpr"),
                    "f1": cand_strict.get("f1"),
                    "latency_p99": cand_strict.get("latency_p99"),
                    "mcnemar_p": metrics.get("mcnemar_p"),
                }
            )
        return summaries

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and its samples. Returns True if a run was removed."""
        with closing(self._connect()) as conn:
            cur = conn.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM sample_results WHERE run_id=?", (run_id,))
            conn.commit()
            return cur.rowcount > 0

    def update_run_meta(self, run_id: str, tag: str | None = None, note: str | None = None) -> bool:
        """Update the tag and/or note for a run. Returns True if the run exists."""
        sets, params = [], []
        if tag is not None:
            sets.append("tag=?")
            params.append(tag)
        if note is not None:
            sets.append("note=?")
            params.append(note)
        if not sets:
            return True
        params.append(run_id)
        with closing(self._connect()) as conn:
            cur = conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE run_id=?", params)
            conn.commit()
            return cur.rowcount > 0

    def latest_run(self) -> EvalResults | None:
        """Return the most recently saved EvalResults, or None if empty."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT {self._RUN_COLS} FROM runs ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return self._row_to_results(row)

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

    def _load_sample_results(self, run_id: str) -> list[dict[str, Any]]:
        """Read persisted per-sample rows for a run, ordered by row index."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT text, label, category, language, baseline_pred, candidate_pred, "
                "baseline_score, candidate_score, baseline_latency_ms, candidate_latency_ms, "
                "attack_type "
                "FROM sample_results WHERE run_id=? ORDER BY row_idx",
                (run_id,),
            ).fetchall()
        return [
            {
                "text": text,
                "label": label,
                "category": category,
                "language": language,
                "baseline_pred": baseline_pred,
                "candidate_pred": candidate_pred,
                "baseline_score": baseline_score,
                "candidate_score": candidate_score,
                "baseline_latency_ms": baseline_latency_ms if baseline_latency_ms is not None else 0.0,
                "candidate_latency_ms": candidate_latency_ms if candidate_latency_ms is not None else 0.0,
                "attack_type": attack_type,
            }
            for (text, label, category, language, baseline_pred, candidate_pred,
                 baseline_score, candidate_score, baseline_latency_ms, candidate_latency_ms,
                 attack_type) in rows
        ]

    def _row_to_results(self, row: tuple[Any, ...]) -> EvalResults:
        """Reconstruct an EvalResults from a DB row."""
        run_id, timestamp, dataset_sha, git_commit, baseline, candidate, metrics_json = row
        metrics = json.loads(metrics_json) if metrics_json else {}
        d = {
            "run_id": run_id,
            "timestamp": timestamp,
            "dataset_sha": dataset_sha or "",
            "git_commit": git_commit or "",
            "baseline_name": baseline or "",
            "candidate_name": candidate or "",
            "baseline_metrics": metrics.get("baseline_metrics", {}),
            "candidate_metrics": metrics.get("candidate_metrics", {}),
            "baseline_slices": metrics.get("baseline_slices", {}),
            "candidate_slices": metrics.get("candidate_slices", {}),
            "baseline_attack_slices": metrics.get("baseline_attack_slices", {}),
            "candidate_attack_slices": metrics.get("candidate_attack_slices", {}),
            "sample_results": self._load_sample_results(run_id),
            "mcnemar_p": metrics.get("mcnemar_p"),
            "judge_agreement_rate": metrics.get("judge_agreement_rate"),
        }
        return EvalResults.from_dict(d)
