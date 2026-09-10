"""
Language router (R14 routing, R19 cross-language fallback)

At search time, BM25 queries must hit the language-specific tsvector column
that matches the query's language (see .claude/rules/api-conventions.md) —
querying both columns as a fallback without going through this explicit
cross-language path is forbidden.

R19 fallback: if primary-language results have fewer than `min_results`
items above the `score_threshold`, re-query in the other language and
include those results as secondary (BM25 weight 0.5× in the RRF fusion —
see rrf.py). The threshold value isn't specified by the client
(REQUIREMENTS.md §3, item 7) so we use a sensible default.
"""

from langdetect import detect, DetectorFactory
from loguru import logger

DetectorFactory.seed = 0

FALLBACK_SCORE_THRESHOLD = 0.01
FALLBACK_MIN_RESULTS = 3


def detect_query_language(query: str) -> str:
    if not query or not query.strip():
        return "hu"
    try:
        detected = detect(query)
    except Exception:
        return "hu"
    if detected == "hu":
        return "hu"
    if detected in ("en", "en-US", "en-GB"):
        return "en"
    return "hu"


def other_language(lang: str) -> str:
    return "en" if lang == "hu" else "hu"


def bm25_column(lang: str) -> str:
    return f"bm25_tokens_{lang}"


def should_fallback(primary_results: list, score_threshold: float = FALLBACK_SCORE_THRESHOLD) -> bool:
    above = [r for r in primary_results if r.get("bm25_rank_score", 0) >= score_threshold]
    needs_fallback = len(above) < FALLBACK_MIN_RESULTS
    if needs_fallback:
        logger.info(
            f"EVIDENCE_API_CROSS_LANGUAGE_FALLBACK: "
            f"primary_above_threshold={len(above)} "
            f"min_required={FALLBACK_MIN_RESULTS} — triggering secondary-language search"
        )
    return needs_fallback
