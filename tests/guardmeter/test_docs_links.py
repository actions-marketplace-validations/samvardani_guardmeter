"""Every relative markdown link in the docs must resolve to a file in the repo.

Walks README.md, CONTRIBUTING.md, docs/**, and the dataset cards, extracts
`[text](target)` / `![alt](target)` links, and fails on any local target that
does not exist. External (http/https/mailto), anchor-only (#…), and template
(`{{…}}`) links are skipped.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

MD_FILES = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    *sorted(ROOT.glob("docs/**/*.md")),
    *sorted(ROOT.glob("dataset/**/DATASET_CARD.md")),
]

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _targets(md: Path) -> list[str]:
    out = []
    for raw in LINK_RE.findall(md.read_text(encoding="utf-8")):
        target = raw.strip().split()[0].strip("<>")          # drop optional "title"
        target = target.split("#", 1)[0]                     # drop anchor
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if "{{" in target or "${" in target:                 # templated example, not a real path
            continue
        out.append(target)
    return out


@pytest.mark.parametrize("md", MD_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_markdown_links_resolve(md: Path) -> None:
    missing = [t for t in _targets(md) if not (md.parent / t).resolve().exists()]
    assert not missing, f"{md.relative_to(ROOT)} has broken local links: {missing}"
