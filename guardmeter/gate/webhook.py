"""Fire-and-forget webhook notification for gate failures (stdlib only)."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from guardmeter.core.redact import redact

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 5.0


def notify_webhook(url: str, payload: dict[str, Any], timeout: float = DEFAULT_TIMEOUT_S) -> bool:
    """POST ``payload`` as JSON to ``url``. Never raises; returns success.

    A webhook failure must not fail the gate command, so all errors are caught
    and logged (with secrets redacted).
    """
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 (webhook errors must never fail the gate)
        logger.warning("gate webhook POST failed: %s", redact(str(exc)))
        return False
