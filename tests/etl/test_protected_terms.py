"""Tests for protected terms masking (R8, AC-2)."""

import json

import pytest

from bilingual_etl.nlp.protected_terms import ProtectedTermsMasker, load_whitelist


@pytest.fixture
def whitelist_path(tmp_path):
    terms = ["ISO 9001", "Piranha", "ABS", "Bunting", "3M"]
    path = tmp_path / "test_whitelist.json"
    path.write_text(json.dumps(terms), encoding="utf-8")
    return path


@pytest.fixture
def masker(whitelist_path):
    return ProtectedTermsMasker(whitelist_path)


class TestLoadWhitelist:
    def test_loads_json_list(self, whitelist_path):
        terms = load_whitelist(whitelist_path)
        assert "ISO 9001" in terms
        assert len(terms) == 5


class TestMask:
    def test_masks_single_term(self, masker):
        masked, mapping = masker.mask("We use Bunting magnets.")
        assert "Bunting" not in masked
        assert "zzzptermzzz0zzz" in masked
        assert mapping["zzzptermzzz0zzz"] == "Bunting"

    def test_masks_multiple_terms(self, masker):
        masked, mapping = masker.mask("Piranha pumps, ABS certified, ISO 9001 quality.")
        assert len(mapping) == 3
        assert "Piranha" not in masked
        assert "ABS" not in masked
        assert "ISO 9001" not in masked

    def test_longest_match_wins(self, masker):
        # "ABS" alone is in the whitelist; ensure it doesn't false-match inside other words
        masked, mapping = masker.mask("The absolute value of ABS is clear.")
        assert "absolute" in masked  # untouched — not a word-boundary match
        assert len(mapping) == 1
        assert list(mapping.values())[0] == "ABS"

    def test_no_match_returns_original(self, masker):
        text = "This text has no protected terms at all."
        masked, mapping = masker.mask(text)
        assert masked == text
        assert mapping == {}

    def test_empty_string(self, masker):
        masked, mapping = masker.mask("")
        assert masked == ""
        assert mapping == {}

    def test_case_insensitive_match(self, masker):
        masked, mapping = masker.mask("we use bunting magnets")
        assert len(mapping) == 1
        assert mapping["zzzptermzzz0zzz"] == "bunting"


class TestUnmask:
    def test_round_trip_preserves_original(self, masker):
        text = "Piranha pumps and ABS parts, ISO 9001 certified."
        masked, mapping = masker.mask(text)
        restored = masker.unmask(masked, mapping)
        assert restored == text

    def test_round_trip_survives_lowercasing(self, masker):
        """Simulates a lemmatizer lowercasing unknown placeholder tokens.

        The surrounding text stays lowercased (that's the lemmatizer's job),
        but the protected term itself must come back with its ORIGINAL casing.
        """
        text = "Bunting magnets are ISO 9001 certified."
        masked, mapping = masker.mask(text)
        lowered = masked.lower()
        restored = masker.unmask(lowered, mapping)
        assert restored == "Bunting magnets are ISO 9001 certified."

    def test_unmask_with_empty_mapping(self, masker):
        text = "No placeholders here."
        assert masker.unmask(text, {}) == text

    def test_bunting_survives_full_cycle(self, masker):
        """The AC-2 acceptance scenario: 'Bunting' must never become 'bunt'."""
        text = "Bunting is a leading magnet brand."
        masked, mapping = masker.mask(text)
        # Simulate lemmatization mangling anything NOT masked
        fake_lemmatized = masked.replace("magnet", "magnetiz").replace("brand", "brand")
        restored = masker.unmask(fake_lemmatized, mapping)
        assert "Bunting" in restored
        assert "bunt" not in restored.lower().replace("bunting", "")
