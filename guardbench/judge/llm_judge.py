"""LLM-as-judge implementation supporting Claude and OpenAI models."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Optional

from guardbench.core.guard import GuardResult
from guardbench.judge.base import Judge, JudgeVerdict
from guardbench.judge.prompts import SAFETY_JUDGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_DEFAULT_RATE_RPS = 1.0  # requests per second


@dataclass
class BatchJudgeSummary:
    """Result of a batch judge run.

    ``verdicts`` is index-aligned with the input; entries are ``None`` where the
    judge API call failed. ``errors`` counts those failures so callers never
    mistake an API error for judge agreement. ``agreement_rate`` is computed over
    successful verdicts only (``None`` when there are none).
    """

    verdicts: List[Optional[JudgeVerdict]]
    errors: int
    agreement_rate: Optional[float]


class LLMJudge(Judge):
    """Judge that uses a Claude or OpenAI model to evaluate guard predictions.

    Model auto-detection: 'claude-*' → Anthropic SDK; 'gpt-*' or 'o1-*' → OpenAI SDK.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
        rate_rps: float = _DEFAULT_RATE_RPS,
    ) -> None:
        """Initialise with model name, optional API key, and rate limit."""
        self.model = model
        self.api_key = api_key
        self.rate_rps = rate_rps
        self._min_interval = 1.0 / rate_rps if rate_rps > 0 else 0.0
        self._last_call: float = 0.0

        if model.startswith("claude"):
            self._backend = "anthropic"
        elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
            self._backend = "openai"
        else:
            self._backend = "anthropic"  # default

    def _rate_limit(self) -> None:
        """Sleep if needed to respect the rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _build_user_message(self, text: str, guard_result: GuardResult) -> str:
        return (
            f"Text: {text!r}\n"
            f"Guard prediction: {guard_result.prediction!r}\n"
            f"Guard score: {guard_result.score:.3f}\n\n"
            "Please evaluate this prediction and respond with JSON."
        )

    def _parse_verdict(self, content: str) -> JudgeVerdict:
        """Parse the LLM's JSON response into a JudgeVerdict."""
        content = content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(content)
        return JudgeVerdict(
            agrees=bool(data.get("agrees", True)),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=str(data.get("reasoning", "")),
            suggested_label=str(data.get("suggested_label", "benign")),
        )

    def _call_anthropic(self, user_message: str) -> str:
        """Call the Anthropic API and return the text response."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install sea-guard[llm]")

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=256,
            system=SAFETY_JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def _call_openai(self, user_message: str) -> str:
        """Call the OpenAI API and return the text response."""
        try:
            import openai
        except ImportError:
            raise ImportError("openai package required. Install with: pip install sea-guard[llm]")

        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SAFETY_JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def evaluate(self, text: str, guard_result: GuardResult) -> JudgeVerdict:
        """Evaluate a single text + guard_result and return a JudgeVerdict."""
        self._rate_limit()
        user_message = self._build_user_message(text, guard_result)
        if self._backend == "anthropic":
            content = self._call_anthropic(user_message)
        else:
            content = self._call_openai(user_message)
        return self._parse_verdict(content)

    def evaluate_batch(
        self,
        texts: List[str],
        guard_results: List[GuardResult],
        max_workers: int = 4,
    ) -> BatchJudgeSummary:
        """Evaluate multiple texts in parallel (respecting rate limit per worker).

        A judge API error is recorded as a ``None`` verdict and counted in
        ``errors`` — it is never silently converted into agreement.
        """
        verdicts: List[Optional[JudgeVerdict]] = [None] * len(texts)
        errors = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.evaluate, text, gr): idx
                for idx, (text, gr) in enumerate(zip(texts, guard_results))
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    verdicts[idx] = future.result()
                except Exception as exc:
                    logger.warning("Judge failed on sample %d: %s", idx, exc)
                    verdicts[idx] = None
                    errors += 1
        successful = [v for v in verdicts if v is not None]
        agreement_rate = (
            round(sum(1 for v in successful if v.agrees) / len(successful), 4)
            if successful else None
        )
        return BatchJudgeSummary(verdicts=verdicts, errors=errors, agreement_rate=agreement_rate)
