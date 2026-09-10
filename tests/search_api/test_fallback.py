"""Tests for cross-language fallback (R19)."""

from search_api.services.language_router import (
    bm25_column,
    detect_query_language,
    other_language,
    should_fallback,
)


def test_detect_hungarian():
    assert detect_query_language("külső árnyékoló redőny") == "hu"


def test_detect_english():
    assert detect_query_language(
        "I am looking for an industrial pump manufacturer that provides maintenance services"
    ) == "en"


def test_empty_defaults_to_hu():
    assert detect_query_language("") == "hu"


def test_other_language():
    assert other_language("hu") == "en"
    assert other_language("en") == "hu"


def test_bm25_column():
    assert bm25_column("hu") == "bm25_tokens_hu"
    assert bm25_column("en") == "bm25_tokens_en"


def test_should_fallback_when_too_few_results():
    results = [{"bm25_rank_score": 0.001}]
    assert should_fallback(results) is True


def test_should_not_fallback_when_enough_results():
    results = [
        {"bm25_rank_score": 0.5},
        {"bm25_rank_score": 0.3},
        {"bm25_rank_score": 0.1},
    ]
    assert should_fallback(results) is False


def test_should_fallback_when_empty():
    assert should_fallback([]) is True
