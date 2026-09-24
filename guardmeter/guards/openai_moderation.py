"""OpenAI Moderation API guard adapter.

Registered as ``openai``. Unlike the chat-classifier adapters (``anthropic`` /
``openai-chat``), the Moderation endpoint takes no instructions and returns only
category flags, so it cannot be hijacked by the sample text — results carry
``metadata["hijackable"] = False`` to say so.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.registry import register

logger = logging.getLogger(__name__)

# OpenAI → GuardMeter category mapping
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

    Raises ImportError in the constructor when openai is not installed.
    """

    name: str = "openai"
    version: str = "1.1.0"
    is_remote: bool = True

    def __init__(self, api_key: str | None = None, model: str = "omni-moderation-latest") -> None:
        """Initialise with optional API key and moderation model name."""
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAIModerationGuard. "
                "Install it with: pip install guardmeter[llm]"
            )
        import openai as _openai
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("No OpenAI API key: pass api_key= or set OPENAI_API_KEY.")
        self._client = _openai.OpenAI(api_key=key)
        self.model = model

    def describe(self) -> dict[str, Any]:
        """Reproducibility metadata: model and verdict mode."""
        return {"name": self.name, "version": self.version, "model": self.model,
                "mode": "moderation_api"}

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
            # The Moderation endpoint follows no instructions in the input.
            metadata={"hijackable": False},
        )


register("openai", OpenAIModerationGuard)
