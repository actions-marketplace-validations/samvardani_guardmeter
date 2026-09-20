"""IO utilities: config loading, path resolution, file hashing, git commit SHA."""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config.yaml from the project root (or a given path)."""
    cfg_path = path or (ROOT / "config.yaml")
    if not cfg_path.exists():
        return {}
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def resolve_dataset_path(cfg: dict[str, Any]) -> Path:
    """Resolve the dataset path from config, relative to project root."""
    raw = cfg.get("dataset_path", "./dataset/sample.csv")
    p = Path(raw)
    if not p.is_absolute():
        p = (ROOT / raw).resolve()
    return p


def hash_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_content(content: bytes) -> str:
    """Compute SHA-256 hex digest of arbitrary bytes."""
    return hashlib.sha256(content).hexdigest()


def git_commit_sha() -> str:
    """Return the current git HEAD commit SHA, or 'unknown' on failure."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT
        ).decode().strip()
    except Exception:  # noqa: BLE001 (intentional resilience boundary)
        return "unknown"


def new_run_id() -> str:
    """Generate a new unique run identifier (UUID4 hex string)."""
    return str(uuid.uuid4())
