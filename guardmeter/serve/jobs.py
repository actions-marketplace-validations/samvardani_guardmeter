"""Background job manager for /api/compare (stdlib threads only)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from guardmeter.core.io_utils import new_run_id
from guardmeter.core.redact import redact

logger = logging.getLogger(__name__)


class JobManager:
    """Runs comparisons on background threads and tracks their progress."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _set(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            self._jobs.setdefault(job_id, {}).update(fields)

    def start_compare(self, store: Any, baseline: str, candidate: str, dataset: str) -> str:
        """Kick off a compare in a background thread; return the job id."""
        job_id = new_run_id()
        self._set(job_id, status="running", progress=0.0, run_id=None, error=None)
        thread = threading.Thread(
            target=self._run_compare,
            args=(job_id, store, baseline, candidate, dataset),
            daemon=True,
        )
        thread.start()
        return job_id

    def _run_compare(self, job_id: str, store: Any, baseline: str, candidate: str, dataset: str) -> None:
        try:
            from guardmeter.core.registry import get_guard, import_builtin_guards
            from guardmeter.data.loader import load_dataset
            from guardmeter.engine.evaluator import EvalConfig, Evaluator

            import_builtin_guards()
            records = load_dataset(dataset)
            base_guard = get_guard(baseline)
            cand_guard = get_guard(candidate)

            def on_progress(done: int, total: int) -> None:
                self._set(job_id, progress=round(done / total, 4) if total else 1.0)

            evaluator = Evaluator(base_guard, cand_guard, records, EvalConfig(), on_progress=on_progress)
            results = evaluator.run()
            store.save_run(results)
            self._set(job_id, status="done", progress=1.0, run_id=results.run_id)
        except Exception as exc:  # noqa: BLE001 (surface any failure as job error, never crash the server)
            logger.warning("compare job %s failed: %s", job_id, redact(str(exc)))
            self._set(job_id, status="error", error=redact(str(exc)))
