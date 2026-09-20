"""OpenAI Moderation API guard adapter."""

from __future__ import annotations

import logging
import time
from typing import Any

from guardbench.core.guard import Guard, GuardResult
from guardbench.core.registry import register

logger = logging.getLogger(__name__)

# OpenAI → GuardBench category mapping
_CATEGORY_MAP = {
    "harassment": "hate",
    "harassment/threatening": "violence",
    "hate": "hate",
    "hate/threatening": "violence",
    "self-harm": "self_harm",
    "self-harm/intent": "self_harm",
    "self-harm/instructions": "self_harm",
    "sexual": "pii",
    "sexual/minors": "minors",
    "violence": "violence",
    "violence/graphic": "violence",
}


class OpenAIModerationGuard(Guard):
    """Guard that calls the OpenAI Moderation API to classify text.

    Raises ImportError at import time when openai is not installed.
    """

    name: str = "openai"
    version: str = "1.0.0"

    def __init__(self, api_key: str | None = None, model: str = "text-moderation-latest") -> None:
        """Initialise with optional API key and moderation model name."""
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAIModerationGuard. "
                "Install it with: pip install sea-guard[llm]"
            )
        import openai as _openai
        self._client = _openai.OpenAI(api_key=api_key)
        self.model = model

    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Call the OpenAI Moderation API and return a GuardResult."""
        start = time.perf_counter()
        response = self._client.moderations.create(input=text, model=self.model)
        result = response.results[0]
        latency_ms = int((time.perf_counter() - start) * 1000)

        prediction = "flag" if result.flagged else "pass"
        categories: list[str] = []
        if result.flagged and result.categories:
            for oai_cat, flagged in result.categories.model_dump().items():
                if flagged:
                    gb_cat = _CATEGORY_MAP.get(oai_cat, oai_cat)
                    if gb_cat not in categories:
                        categories.append(gb_cat)

        # Use max category score as overall score
        scores = result.category_scores.model_dump() if result.category_scores else {}
        score = max(scores.values()) if scores else (1.0 if prediction == "flag" else 0.0)

        return GuardResult(
            prediction=prediction,
            score=float(score),
            latency_ms=latency_ms,
            categories=categories,
        )


register("openai", OpenAIModerationGuard)
