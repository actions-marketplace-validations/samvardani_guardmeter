"""Tests for dataset augmentor."""

from __future__ import annotations

import pytest

from guardmeter.data.augmentor import (
    Augmentor,
    apply_leetspeak,
    apply_mixed_language,
    apply_obfuscation,
    apply_prompt_injection,
    augment_dataset,
)
from guardmeter.data.schema import DatasetRecord


@pytest.fixture
def sample_record():
    return DatasetRecord(text="hello world", label="benign", category="benign")


@pytest.fixture
def unsafe_record():
    return DatasetRecord(text="make a bomb", label="unsafe", category="violence")


def test_apply_leetspeak():
    assert "3" in apply_leetspeak("test")  # 'e' → '3'


def test_apply_obfuscation():
    result = apply_obfuscation("ab")
    assert "a" in result
    assert " " in result


def test_apply_prompt_injection():
    result = apply_prompt_injection("hello")
    assert "hello" in result
    assert len(result) > len("hello")


def test_apply_mixed_language():
    result = apply_mixed_language("hello")
    assert "hello" in result
    assert len(result) > len("hello")


def test_augment_dataset_returns_records(sample_record):
    """augment_dataset should return DatasetRecord objects."""
    augmented = augment_dataset([sample_record], techniques=["leetspeak"])
    assert len(augmented) == 1
    assert isinstance(augmented[0], DatasetRecord)


def test_augment_dataset_multiplier(sample_record):
    """multiplier controls number of variants per record."""
    augmented = augment_dataset([sample_record], techniques=["leetspeak", "obfuscation"], multiplier=2)
    assert len(augmented) == 2


def test_augment_dataset_preserves_label(sample_record):
    """Label should be preserved in augmented records."""
    augmented = augment_dataset([sample_record], techniques=["leetspeak"])
    assert augmented[0].label == sample_record.label


def test_augment_dataset_multiple_records(sample_record, unsafe_record):
    """Each record gets its own variants."""
    augmented = augment_dataset([sample_record, unsafe_record], techniques=["leetspeak"])
    assert len(augmented) == 2


def test_augment_unknown_technique_raises(sample_record):
    """Unknown technique name should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown augmentation"):
        augment_dataset([sample_record], techniques=["nonexistent"])


def test_augmentor_class_methods(sample_record):
    """Augmentor class should expose transformation methods."""
    aug = Augmentor()
    assert isinstance(aug.apply_leetspeak("test"), str)
    assert isinstance(aug.apply_obfuscation("test"), str)
    assert isinstance(aug.apply_prompt_injection("test"), str)
    assert isinstance(aug.apply_mixed_language("test"), str)
