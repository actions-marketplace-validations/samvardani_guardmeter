"""Abstract base class and verdict type for LLM judges."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from guardmeter.core.guard import GuardResult


@dataclass
class JudgeVerdict:
    """Verdict produced by an LLM judge evaluating a guard's prediction."""

    agrees: bool          # does the judge agree with the guard's prediction?
    confidence: float     # 0.0 – 1.0
    reasoning: str
    suggested_label: str  # "benign" | "borderline" | "unsafe"


class Judge(ABC):
    """Abstract base class for LLM-as-judge implementations."""

    @abstractmethod
    def evaluate(self, text: str, guard_result: GuardResult) -> JudgeVerdict:
        """Evaluate a guard's prediction on a text and return a JudgeVerdict."""
        ...
