"""Tests for `guardmeter dataset fetch` (network mocked)."""

from __future__ import annotations

import hashlib

import pytest

from guardmeter.data import fetch as fetch_mod
from guardmeter.data.fetch import AGENTIC_V1, RELEASES, fetch_dataset


def test_registry_and_urls():
    assert "agentic-v1" in RELEASES
    url = AGENTIC_V1.asset_url("data.jsonl")
    assert url.endswith(f"/releases/download/{AGENTIC_V1.tag}/data.jsonl")


def test_data_asset_pins_sha256():
    data_asset = next(a for a in AGENTIC_V1.assets if a.filename == "data.jsonl")
    assert data_asset.sha256 and len(data_asset.sha256) == 64


def test_fetch_writes_verified_files(tmp_path, monkeypatch):
    payloads = {
        "data.jsonl": b'{"id":"x","text":"hi","label":"benign","category":"benign","language":"en"}\n',
        "DATASET_CARD.md": b"# Card\n",
    }
    # Pin the constant to the fake payload's real digest so verification passes.
    real_sha = hashlib.sha256(payloads["data.jsonl"]).hexdigest()
    monkeypatch.setattr(
        fetch_mod, "AGENTIC_V1",
        fetch_mod.DatasetRelease(
            name="agentic-v1", tag="v9.9.9", dest="dataset/agentic/v1",
            assets=(
                fetch_mod.DatasetAsset("data.jsonl", real_sha),
                fetch_mod.DatasetAsset("DATASET_CARD.md", None),
            ),
        ),
    )
    monkeypatch.setitem(fetch_mod.RELEASES, "agentic-v1", fetch_mod.AGENTIC_V1)
    monkeypatch.setattr(fetch_mod, "_download", lambda url: payloads[url.rsplit("/", 1)[-1]])

    written = fetch_dataset("agentic-v1", tmp_path)
    assert len(written) == 2
    out = tmp_path / "dataset" / "agentic" / "v1"
    assert (out / "data.jsonl").read_bytes() == payloads["data.jsonl"]
    assert (out / "DATASET_CARD.md").read_bytes() == payloads["DATASET_CARD.md"]


def test_fetch_rejects_sha256_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_mod, "_download", lambda url: b"tampered content")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        fetch_dataset("agentic-v1", tmp_path)


def test_fetch_unknown_dataset(tmp_path):
    with pytest.raises(ValueError, match="Unknown dataset"):
        fetch_dataset("nope", tmp_path)


def test_agentic_v1_assets_match_repo_files() -> None:
    """Every pinned asset must match the frozen file in the repo, and the
    fetch registry must carry everything a user needs to run the gate."""
    import hashlib
    from pathlib import Path

    repo_dir = Path(__file__).resolve().parents[2] / "dataset" / "agentic" / "v1"
    names = {a.filename for a in AGENTIC_V1.assets}
    assert {"data.jsonl", "DATASET_CARD.md", "gate.agentic.json", "LICENSE"} <= names
    for asset in AGENTIC_V1.assets:
        if asset.sha256 is None:
            continue
        actual = hashlib.sha256((repo_dir / asset.filename).read_bytes()).hexdigest()
        assert actual == asset.sha256, f"{asset.filename} changed but its pin did not"
