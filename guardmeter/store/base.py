"""Abstract base class for run history storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from guardmeter.engine.results import EvalResults


class RunStore(ABC):
    """Abstract interface for persisting and retrieving evaluation run history."""

    @abstractmethod
    def save_run(self, results: EvalResults) -> None:
        """Persist an EvalResults object."""
        ...

    @abstractmethod
    def get_run(self, run_id: str) -> EvalResults:
        """Retrieve an EvalResults by run_id. Raises KeyError if not found."""
        ...

    @abstractmethod
    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return summary dicts for the most recent runs, newest first."""
        ...

    @abstractmethod
    def latest_run(self, exclude_run_id: str | None = None) -> EvalResults | None:
        """Return the most recently saved EvalResults, optionally excluding one run."""
        ...

    @abstractmethod
    def compare_runs(self, run_id_a: str, run_id_b: str) -> dict[str, Any]:
        """Return a delta dict comparing two runs' candidate metrics."""
        ...
