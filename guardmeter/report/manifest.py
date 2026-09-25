"""Report integrity manifest: sha256 of generated HTML for tamper detection."""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

from guardmeter import __version__

MANIFEST_NAME = "MANIFEST.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(
    report_dir: Path | str,
    *,
    run_id: str | None = None,
    dataset_sha: str | None = None,
    git_commit: str | None = None,
    include: str = "*.html",
) -> Path:
    """Write MANIFEST.json hashing every file matching ``include`` in ``report_dir``.

    ``include="*"`` hashes every file (used by the evidence pack); the manifest
    itself is always excluded.
    """
    report_dir = Path(report_dir)
    files = {
        p.name: _sha256(p)
        for p in sorted(report_dir.glob(include))
        if p.is_file() and p.name != MANIFEST_NAME
    }
    manifest = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "guardmeter_version": __version__,
        "run_id": run_id,
        "dataset_sha": dataset_sha,
        "git_commit": git_commit,
        "files": files,
    }
    out = report_dir / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def verify_manifest(report_dir: Path | str) -> tuple[bool, list[str]]:
    """Recompute hashes and return (ok, problems). ok is False on any mismatch."""
    report_dir = Path(report_dir)
    mpath = report_dir / MANIFEST_NAME
    if not mpath.exists():
        return False, [f"{MANIFEST_NAME} not found in {report_dir}"]

    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        return False, [f"{MANIFEST_NAME} is not valid JSON: {exc}"]

    problems: list[str] = []
    files = manifest.get("files", {})
    if not files:
        problems.append("manifest lists no files")
    for name, expected in files.items():
        fp = report_dir / name
        if not fp.exists():
            problems.append(f"missing file: {name}")
            continue
        if _sha256(fp) != expected:
            problems.append(f"hash mismatch: {name}")
    return (not problems), problems
