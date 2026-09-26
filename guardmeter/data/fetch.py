"""Fetch repo-artifact datasets from tagged GitHub release assets.

The agentic dataset is intentionally *not* bundled in the wheel — it is a
research artifact with its own licence and lifecycle. `guardmeter dataset fetch
agentic-v1` downloads it from the GitHub release assets into
``./dataset/agentic/v1/`` and verifies the data file against a sha256 constant
baked in here, so an installed wheel can pull the exact frozen dataset.
"""

from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_REPO = "samvardani/guardmeter"


@dataclass(frozen=True)
class DatasetAsset:
    """A single downloadable dataset file and its expected sha256 (None = unchecked)."""

    filename: str
    sha256: str | None


@dataclass(frozen=True)
class DatasetRelease:
    """A named dataset published as assets on a tagged GitHub release."""

    name: str
    tag: str
    dest: str  # path (relative to cwd) the files are written into
    assets: tuple[DatasetAsset, ...]

    def asset_url(self, filename: str) -> str:
        """GitHub release-asset download URL for one file."""
        return f"https://github.com/{_REPO}/releases/download/{self.tag}/{filename}"


# Registry of fetchable datasets. sha256 pins the exact frozen data file; the
# card is unpinned (prose may get typo fixes within a release without a re-cut).
AGENTIC_V1 = DatasetRelease(
    name="agentic-v1",
    tag="v0.7.0",
    dest="dataset/agentic/v1",
    assets=(
        DatasetAsset(
            "data.jsonl",
            "012507e611fe1140628dab8bc6502ae312507d448d7dcd12e42b3df135279347",
        ),
        DatasetAsset("DATASET_CARD.md", None),
        # Recommended gate policy and the dataset licence are frozen with v1.
        DatasetAsset(
            "gate.agentic.json",
            "aae00f9867d7e26df6f4dc3092f92f6af77c1338d0ea0a9fdb6196df2a37225a",
        ),
        DatasetAsset(
            "LICENSE",
            "ba5ce8f69442c75fc5e314d6e80b76922d76e1a7861d9976654a368bdb29004f",
        ),
    ),
)

AGENTIC_V2 = DatasetRelease(
    name="agentic-v2",
    tag="v0.10.0",
    dest="dataset/agentic/v2",
    assets=(
        DatasetAsset(
            "data.jsonl",
            "dca9880037b5e03a784130539600ed7fb9ac5168a46752eef68c1cc99ed511f7",
        ),
        DatasetAsset("DATASET_CARD.md", None),
        DatasetAsset(
            "gate.agentic.json",
            "b4893adf58ddeed77d2588bb12fdd8ff2445507641724e9e4b9cf9a6a087af7f",
        ),
        DatasetAsset(
            "LICENSE",
            "298e8ed304723a58c79165136adbca9bad39a9d4d12f1f54046a6d9ffa6c0bfc",
        ),
    ),
)

RELEASES: dict[str, DatasetRelease] = {AGENTIC_V1.name: AGENTIC_V1, AGENTIC_V2.name: AGENTIC_V2}


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url) as resp:
        return resp.read()


def fetch_dataset(name: str, dest_root: str | Path = ".") -> list[Path]:
    """Download ``name``'s assets into ``dest_root/<release.dest>/``.

    Verifies the sha256 of any asset that pins one; raises ValueError on a
    mismatch (and writes nothing for that file). Returns the written paths.
    """
    if name not in RELEASES:
        raise ValueError(f"Unknown dataset '{name}'. Known: {', '.join(sorted(RELEASES))}")
    release = RELEASES[name]
    out_dir = Path(dest_root) / release.dest
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for asset in release.assets:
        data = _download(release.asset_url(asset.filename))
        if asset.sha256 is not None:
            got = hashlib.sha256(data).hexdigest()
            if got != asset.sha256:
                raise ValueError(
                    f"sha256 mismatch for {asset.filename}: "
                    f"expected {asset.sha256}, got {got}"
                )
        path = out_dir / asset.filename
        path.write_bytes(data)
        written.append(path)
    return written
