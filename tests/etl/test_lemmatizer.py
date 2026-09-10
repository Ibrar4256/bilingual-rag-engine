"""Tests for lemmatization + protected terms integration (R9 partial, AC-2)."""

import pytest

from bilingual_etl.nlp.lemmatizer import lemmatize, lemmatize_for_bm25
from bilingual_etl.nlp.protected_terms import ProtectedTermsMasker


@pytest.fixture(scope="module")
def masker(tmp_path_factory):
    import json

    terms = ["ISO 9001", "Piranha", "ABS", "Bunting", "Zultzer Pumpen Kft."]
    path = tmp_path_factory.mktemp("data") / "test_whitelist.json"
    path.write_text(json.dumps(terms), encoding="utf-8")
    return ProtectedTermsMasker(path)


class TestLemmatize:
    def test_english_lemmatization(self):
        result = lemmatize("The companies are manufacturing steel structures.", "en")
        assert "manufacture" in result
        assert "company" in result
        assert "structure" in result

    def test_hungarian_lemmatization(self):
        result = lemmatize("A cégek acélszerkezeteket gyártanak.", "hu")
        assert "cég" in result
        assert "acélszerkezet" in result

    def test_removes_punctuation(self):
        result = lemmatize("Hello, world! How are you?", "en")
        assert "," not in result
        assert "!" not in result
        assert "?" not in result

    def test_removes_stopwords(self):
        result = lemmatize("The company is manufacturing products.", "en")
        assert "the" not in result.split()
        assert "is" not in result.split()

    def test_empty_string(self):
        assert lemmatize("", "en") == ""

    def test_unsupported_language_raises(self):
        with pytest.raises(ValueError, match="Unsupported language"):
            lemmatize("Some text", "fr")


class TestLemmatizeForBm25:
    def test_bunting_survives_lemmatization(self, masker):
        """The AC-2 acceptance scenario: a protected brand name must survive
        the full mask -> lemmatize -> unmask cycle completely unchanged."""
        text = "Bunting produces magnets for several companies."
        result = lemmatize_for_bm25(text, "en", masker)
        assert "Bunting" in result
        assert "produce" in result  # ordinary words still get lemmatized

    def test_iso_9001_survives(self, masker):
        text = "Our products are ISO 9001 certified and manufactured locally."
        result = lemmatize_for_bm25(text, "en", masker)
        assert "ISO 9001" in result
        assert "certify" in result

    def test_real_dataset_brand_piranha(self, masker):
        text = "Piranha pumps are manufactured with ABS components."
        result = lemmatize_for_bm25(text, "en", masker)
        assert "Piranha" in result
        assert "ABS" in result
        assert "pump" in result  # lemmatized ordinary word

    def test_multi_word_protected_term(self, masker):
        text = "Zultzer Pumpen Kft. manufactures industrial pumps."
        result = lemmatize_for_bm25(text, "en", masker)
        assert "Zultzer Pumpen Kft." in result

    def test_hungarian_with_protected_terms(self, masker):
        text = "A Zultzer Pumpen Kft. Piranha szivattyúkat gyárt."
        result = lemmatize_for_bm25(text, "hu", masker)
        assert "Zultzer Pumpen Kft." in result
        assert "Piranha" in result
        assert "szivattyú" in result  # lemmatized ordinary word

    def test_no_protected_terms_still_lemmatizes(self, masker):
        text = "The factory produces many products."
        result = lemmatize_for_bm25(text, "en", masker)
        assert "produce" in result
        assert "product" in result
