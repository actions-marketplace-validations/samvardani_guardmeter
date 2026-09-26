"""Tests for the cross-lingual attack families and bidi handling."""

from __future__ import annotations

from guardmeter.core.redact import has_bidi_controls, redact, reveal_bidi
from guardmeter.data.schema import ATTACK_FAMILIES, DatasetRecord
from guardmeter.data.validate import validate_records


def _rec(**kw):
    base = {"text": "x", "label": "unsafe", "category": "prompt_injection"}
    base.update(kw)
    return DatasetRecord(**base)


def test_six_new_families_registered():
    for fam in ("script_mixing", "transliteration", "language_switch",
                "bidi_override", "translate_then_follow", "cultural_authority"):
        assert fam in ATTACK_FAMILIES
    assert len(ATTACK_FAMILIES) == 14


def test_validator_accepts_known_family():
    problems = validate_records([_rec(id="a", attack_family="script_mixing", target="override")])
    assert not any("unknown attack_family" in p for p in problems)


def test_validator_rejects_unknown_family():
    problems = validate_records([_rec(id="a", attack_family="teleport_attack")])
    assert any("unknown attack_family" in p for p in problems)


def test_reveal_bidi_makes_controls_visible():
    raw = "price: 100\u202e\u2066USD\u2069"  # RLO + isolates
    shown = reveal_bidi(raw)
    assert "\u202e" not in shown
    assert "⟨RLO⟩" in shown and "⟨LRI⟩" in shown


def test_has_bidi_controls():
    assert has_bidi_controls("a\u202eb")
    assert not has_bidi_controls("ordinary text")


def test_redact_reveals_bidi_not_strips():
    out = redact("hidden\u202einstruction")
    assert "\u202e" not in out       # not left raw
    assert "instruction" in out      # not stripped away
    assert "⟨RLO⟩" in out
