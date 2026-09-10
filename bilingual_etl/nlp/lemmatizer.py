"""
Lemmatization for BM25 keyword search (R9, partial)

Lemmatization reduces words to their dictionary base form (e.g. "manufacturing"
-> "manufacture") so a keyword search for one form also matches the others.
Hungarian and English need different models — huspacy for Hungarian
(hu_core_news_lg), spaCy for English (en_core_web_lg) — routed by the
record's detected language. Never cross-apply a model to the wrong language.

This module also wires in Protected Terms masking (R8): the full pipeline for
producing BM25-ready text is mask -> lemmatize -> unmask, in that exact order.
Masking first means the lemmatizer never sees (and can't corrupt) brand names;
unmasking after restores them verbatim in the final token string.

Usage:
    tokens = lemmatize_for_bm25("Bunting magnets are ISO 9001 certified.", "en", masker)
    # "Bunting magnet be ISO 9001 certify"  (ordinary words lemmatized,
    #  protected terms restored exactly as they appeared)
"""

import spacy

from bilingual_etl.nlp.protected_terms import ProtectedTermsMasker

MODEL_NAMES = {
    "hu": "hu_core_news_lg",
    "en": "en_core_web_lg",
}

_model_cache: dict[str, spacy.Language] = {}


def _get_model(language: str) -> spacy.Language:
    if language not in MODEL_NAMES:
        raise ValueError(f"Unsupported language '{language}'. Expected 'hu' or 'en'.")

    if language not in _model_cache:
        _model_cache[language] = spacy.load(MODEL_NAMES[language])
    return _model_cache[language]


def lemmatize(text: str, language: str) -> str:
    if not text:
        return ""

    nlp = _get_model(language)
    doc = nlp(text)
    lemmas = [
        token.lemma_.lower()
        for token in doc
        if not token.is_punct and not token.is_space and not token.is_stop
    ]
    return " ".join(lemmas)


def lemmatize_for_bm25(text: str, language: str, masker: ProtectedTermsMasker) -> str:
    masked_text, mapping = masker.mask(text)
    lemmatized = lemmatize(masked_text, language)
    return masker.unmask(lemmatized, mapping)
