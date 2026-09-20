"""LlamaGuard adapter: supports HuggingFace transformers pipeline and HTTP endpoints."""

from __future__ import annotations

import logging
import time
from typing import Any

from guardbench.core.guard import Guard, GuardResult
from guardbench.core.registry import register

logger = logging.getLogger(__name__)


class LlamaGuardAdapter(Guard):
    """Adapter for Meta LlamaGuard models.

    Supports local HuggingFace transformers pipeline and HTTP endpoints
    (Groq, Fireworks, Together AI, or any OpenAI-compatible API).
    """

    name: str = "llamaguard"
    version: str = "1.0.0"

    def __init__(
        self,
        model: str = "meta-llama/Llama-Guard-3-8B",
        endpoint: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialise with model name, optional HTTP endpoint, and optional API key."""
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key
        self._pipeline: Any = None
        self._http_client: Any = None

        if endpoint:
            self._init_http()
        else:
            self._init_pipeline()

    def _init_http(self) -> None:
        """Initialise an HTTP client for remote endpoint inference."""
        try:
            import httpx  # noqa: F401
            self._http_client = True  # lazy-init actual client per request
        except ImportError:
            raise ImportError("httpx is required for HTTP endpoint mode. pip install httpx")

    def _init_pipeline(self) -> None:
        """Initialise a local HuggingFace transformers pipeline."""
        try:
            from transformers import pipeline  # noqa: F401
        except ImportError:
            raise ImportError(
                "transformers is required for local LlamaGuard inference. "
                "Install with: pip install sea-guard[hf]"
            )

    def _predict_http(self, text: str) -> tuple[str, float]:
        """Send text to the remote endpoint and parse the response."""
        import httpx
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 10,
        }
        response = httpx.post(f"{self.endpoint}/chat/completions", json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip().lower()
        if content.startswith("unsafe"):
            return "flag", 0.9
        return "pass", 0.1

    def _predict_pipeline(self, text: str) -> tuple[str, float]:
        """Run inference via local HuggingFace pipeline."""
        from transformers import pipeline
        if self._pipeline is None:
            self._pipeline = pipeline("text-generation", model=self.model, device_map="auto")
        prompt = f"[INST] {text} [/INST]"
        output = self._pipeline(prompt, max_new_tokens=10, return_full_text=False)
        content = (output[0]["generated_text"] or "").strip().lower()
        if content.startswith("unsafe"):
            return "flag", 0.9
        return "pass", 0.1

    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Score a single text using LlamaGuard and return a GuardResult."""
        start = time.perf_counter()
        if self.endpoint:
            prediction, score = self._predict_http(text)
        else:
            prediction, score = self._predict_pipeline(text)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return GuardResult(
            prediction=prediction,
            score=score,
            latency_ms=latency_ms,
        )


register("llamaguard", LlamaGuardAdapter)
