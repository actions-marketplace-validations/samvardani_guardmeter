"""Generic HTTP guard: call a customer's own safety endpoint over HTTP.

The connector that lets GuardMeter evaluate a guard it doesn't ship. Configure
it entirely from the environment (``GUARDMETER_HTTP_*``) or a YAML/JSON file
(``--baseline-config`` / ``--candidate-config``): the URL, method, headers, a
request-body template with ``{{text}}`` / ``{{context}}`` placeholders, and a
dotted path to the boolean/label field in the response. Non-2xx responses and
timeouts raise, so the evaluator records them as errors (never a silent pass).

Uses only the standard library — no extra dependency to connect an endpoint.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.registry import register

logger = logging.getLogger(__name__)

_DEFAULT_FLAG_VALUES = ("true", "flagged", "unsafe", "block", "blocked", "deny")


def _dig(obj: Any, path: str) -> Any:
    """Follow a dotted path (JSONPath-lite) with string keys and integer indices."""
    cur = obj
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(f"cannot descend into {type(cur).__name__} at {part!r}")
    return cur


class HttpGuard(Guard):
    """Guard backed by an arbitrary HTTP endpoint with configurable I/O mapping."""

    name: str = "http"
    version: str = "1.0.0"
    is_remote: bool = True

    def __init__(
        self,
        url: str | None = None,
        method: str | None = None,
        headers: dict[str, str] | None = None,
        body_template: str | None = None,
        verdict_path: str | None = None,
        flag_values: list[str] | None = None,
        score_path: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """Build from explicit args, falling back to ``GUARDMETER_HTTP_*`` env vars."""
        env = os.environ.get
        resolved_url = url or env("GUARDMETER_HTTP_URL")
        if not resolved_url:
            raise ValueError(
                "HTTP guard needs a URL: set GUARDMETER_HTTP_URL or pass url= "
                "(or use --baseline-config/--candidate-config)."
            )
        self.url: str = resolved_url
        self.method = (method or env("GUARDMETER_HTTP_METHOD") or "POST").upper()
        if headers is None:
            raw = env("GUARDMETER_HTTP_HEADERS")
            headers = json.loads(raw) if raw else {}
        # Expand ${ENV_VAR} in header values (e.g. Authorization from the env).
        self.headers = {k: os.path.expandvars(str(v)) for k, v in headers.items()}
        self.body_template = (
            body_template if body_template is not None
            else env("GUARDMETER_HTTP_BODY") or '{"text": "{{text}}"}'
        )
        self.verdict_path = verdict_path or env("GUARDMETER_HTTP_VERDICT_PATH") or "flagged"
        if flag_values is None:
            raw_fv = env("GUARDMETER_HTTP_FLAG_VALUES")
            flag_values = [v.strip() for v in raw_fv.split(",")] if raw_fv else list(_DEFAULT_FLAG_VALUES)
        self.flag_values = {str(v).strip().lower() for v in flag_values}
        self.score_path = score_path or env("GUARDMETER_HTTP_SCORE_PATH") or None
        self.timeout = timeout if timeout is not None else float(env("GUARDMETER_HTTP_TIMEOUT") or 10.0)

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> HttpGuard:
        """Build from a parsed YAML/JSON config dict (``type: http``)."""
        return cls(
            url=cfg.get("url"),
            method=cfg.get("method"),
            headers=cfg.get("headers"),
            body_template=cfg.get("body") if isinstance(cfg.get("body"), str) else (
                json.dumps(cfg["body"]) if cfg.get("body") is not None else None),
            verdict_path=cfg.get("verdict_path"),
            flag_values=[str(v) for v in cfg["flag_values"]] if cfg.get("flag_values") is not None else None,
            score_path=cfg.get("score_path"),
            timeout=cfg.get("timeout"),
        )

    def describe(self) -> dict[str, Any]:
        """Reproducibility metadata (URL/method/paths — never the headers/secrets)."""
        return {"name": self.name, "version": self.version, "url": self.url,
                "method": self.method, "verdict_path": self.verdict_path,
                "score_path": self.score_path}

    def _render_body(self, text: str, context: str | None) -> bytes:
        # Substitute placeholders with JSON-escaped values so the template stays valid JSON.
        def esc(s: str) -> str:
            return json.dumps(s)[1:-1]
        body = self.body_template.replace("{{text}}", esc(text)).replace(
            "{{context}}", esc(context or ""))
        return body.encode("utf-8")

    def _flagged(self, verdict: Any) -> str:
        if isinstance(verdict, bool):
            return "flag" if verdict else "pass"
        return "flag" if str(verdict).strip().lower() in self.flag_values else "pass"

    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Call the endpoint and map its response to a GuardResult.

        Raises on non-2xx status or timeout so the evaluator records an error.
        """
        start = time.perf_counter()
        headers = {"Content-Type": "application/json", **self.headers}
        data = self._render_body(text, meta.get("context")) if self.method != "GET" else None
        req = urllib.request.Request(self.url, data=data, headers=headers, method=self.method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # non-2xx
            raise RuntimeError(f"HTTP guard {self.url} returned {exc.code}") from exc
        latency_ms = int((time.perf_counter() - start) * 1000)
        if not (200 <= status < 300):
            raise RuntimeError(f"HTTP guard {self.url} returned {status}")

        prediction = self._flagged(_dig(payload, self.verdict_path))
        score: float | None = None
        if self.score_path:
            try:
                score = float(_dig(payload, self.score_path))
            except (KeyError, IndexError, TypeError, ValueError):
                score = None
        if score is None:
            score = 1.0 if prediction == "flag" else 0.0
        return GuardResult(prediction=prediction, score=score, latency_ms=latency_ms)


register("http", HttpGuard)
