"""Native-reviewer workflow and per-language release status for a dataset.

A dataset row starts life as ``review_status="authored"``. Only a named native
reviewer can move it to ``"reviewed"``, via a review packet (``queue`` → a
reviewer fills it in → ``apply``). A language is ``released`` only when ≥ 90% of
its rows are reviewed by a native reviewer *and* the validator passes. The IDE
that authored the rows is not a reviewer and cannot sign anything off.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardmeter.data.schema import DatasetRecord

RELEASE_MIN_REVIEWED = 0.90        # ≥ 90% reviewed to release
MAX_UNREVIEWED_FOR_RELEASE = 0.10  # equivalently, < 10% unreviewed
STATUSES = ("draft", "authored", "in_review", "reviewed", "released")


# ── Manifest ─────────────────────────────────────────────────────────────────

@dataclass
class LanguageEntry:
    rows: int = 0
    families_covered: list[str] = field(default_factory=list)
    status: str = "draft"
    reviewers: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""


def load_manifest(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"dataset": "agentic", "version": "v2", "languages": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_language(manifest: dict[str, Any], code: str, records: list[DatasetRecord]) -> None:
    """Recompute rows/families for a language from its records, preserving review meta."""
    langs = manifest.setdefault("languages", {})
    entry = langs.setdefault(code, {"status": "draft", "reviewers": [], "notes": ""})
    rows = [r for r in records if r.language == code]
    entry["rows"] = len(rows)
    entry["families_covered"] = sorted({r.attack_family for r in rows if r.attack_family})
    if entry.get("status", "draft") == "draft" and rows:
        entry["status"] = "authored"


def reviewed_fraction(records: list[DatasetRecord], code: str) -> float:
    rows = [r for r in records if r.language == code]
    if not rows:
        return 0.0
    return sum(1 for r in rows if r.review_status == "reviewed") / len(rows)


def reviewed_status(records: list[DatasetRecord], code: str) -> str:
    """Manifest status implied by how many of a language's rows are reviewed.

    ``reviewed`` at ≥ RELEASE_MIN_REVIEWED, ``in_review`` when partially
    reviewed (the "partially reviewed" state), else ``authored``/``draft``.
    """
    frac = reviewed_fraction(records, code)
    if frac >= RELEASE_MIN_REVIEWED:
        return "reviewed"
    if frac > 0:
        return "in_review"
    return "authored" if any(r.language == code for r in records) else "draft"


def can_release(records: list[DatasetRecord], code: str, validator_ok: bool) -> tuple[bool, str]:
    """Whether a language may be marked released. Returns (ok, reason)."""
    frac = reviewed_fraction(records, code)
    if frac < RELEASE_MIN_REVIEWED:
        return False, (f"only {frac:.0%} of {code} rows reviewed by a native reviewer "
                       f"(need ≥ {RELEASE_MIN_REVIEWED:.0%})")
    if not validator_ok:
        return False, f"validator does not pass for {code}"
    return True, "eligible"


def status_table(manifest: dict[str, Any], records: list[DatasetRecord] | None = None) -> list[dict[str, Any]]:
    """Rows of language × status × counts × reviewed% for `dataset review status`."""
    out = []
    for code, e in sorted(manifest.get("languages", {}).items()):
        reviewed = reviewed_fraction(records, code) if records is not None else None
        out.append({
            "language": code,
            "status": e.get("status", "draft"),
            "rows": e.get("rows", 0),
            "families": len(e.get("families_covered", [])),
            "reviewers": [rv.get("name") for rv in e.get("reviewers", [])],
            "reviewed_pct": None if reviewed is None else round(reviewed, 3),
        })
    return out


# ── Review packets ───────────────────────────────────────────────────────────

_CHECKLIST = [
    "Label correct (benign / borderline / unsafe)?",
    "Natural native register — not a translation of English?",
    "attack_family correct?",
    "If benign look-alike: is it genuinely hard (shares surface features)?",
]


def build_packet(records: list[DatasetRecord], code: str, reviewer: str) -> tuple[str, str]:
    """Build a review packet for a language: (jsonl, markdown checklist)."""
    rows = [r for r in records if r.language == code and r.review_status != "reviewed"]
    jsonl = "\n".join(json.dumps({
        "id": r.id, "text": r.text, "label": r.label, "category": r.category,
        "attack_family": r.attack_family, "language": r.language, "context": r.context,
        "decision": "accept", "new_label": None, "new_text": None, "reason": None,
    }, ensure_ascii=False) for r in rows)

    md = [f"# Review packet — {code} — reviewer: {reviewer}", "",
          (f"{len(rows)} rows awaiting review. For each, set `decision` in the JSONL to "
           "`accept`, `relabel` (+`new_label`), `rewrite` (+`new_text`), or `reject` (+`reason`)."),
          ""]
    for r in rows:
        md.append(f"## {r.id} — `{r.label}` / `{r.attack_family or '—'}`")
        md.append(f"> {r.text}")
        md.extend(f"- [ ] {item}" for item in _CHECKLIST)
        md.append("")
    return jsonl, "\n".join(md)


def apply_packet(records: list[DatasetRecord], decisions: list[dict[str, Any]],
                 reviewer: str, native: bool, when: str) -> dict[str, Any]:
    """Apply a reviewer's decisions to records in place. Returns a summary.

    accept → reviewed; relabel → set label + reviewed; rewrite → set text +
    reviewed; reject → review_status="rejected". Records a sign-off sha over the
    canonical form of the rows the reviewer accepted/edited.
    """
    by_id = {r.id: r for r in records if r.id}
    counts = {"accept": 0, "relabel": 0, "rewrite": 0, "reject": 0, "missing": 0}
    signed: list[str] = []
    for d in decisions:
        r = by_id.get(str(d.get("id"))) if d.get("id") is not None else None
        if r is None:
            counts["missing"] += 1
            continue
        decision = d.get("decision", "accept")
        if decision == "reject":
            r.review_status = "rejected"
            counts["reject"] += 1
            continue
        if decision == "relabel" and d.get("new_label"):
            r.label = d["new_label"]
            counts["relabel"] += 1
        elif decision == "rewrite" and d.get("new_text"):
            r.text = d["new_text"]
            counts["rewrite"] += 1
        else:
            counts["accept"] += 1
        r.review_status = "reviewed"
        signed.append(f"{r.id}{r.text}{r.label}{r.attack_family}")

    sign_off_sha = hashlib.sha256("".join(sorted(signed)).encode("utf-8")).hexdigest()
    return {
        "reviewer": {"name": reviewer, "native": native, "reviewed_at": when,
                     "rows_reviewed": len(signed), "sign_off_sha": sign_off_sha},
        "counts": counts,
    }
