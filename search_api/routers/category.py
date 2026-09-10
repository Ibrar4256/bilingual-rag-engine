"""
POST /search/category (R15)

Category identification for chatbot pre-qualification — given a free-text
query describing a need, returns matching categories with their `ai_type`
and metadata from the RRF-fused hybrid search.
"""

import json

from fastapi import APIRouter, Query
from loguru import logger
from psycopg2.extras import RealDictCursor

from search_api.db import get_connection
from search_api.models.requests import CategorySearchRequest
from search_api.models.responses import CategoryResult, CategorySearchResponse
from search_api.services.search import search_table, log_search_analytics

router = APIRouter()


@router.get("/search/suggest")
def suggest(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT word
                FROM (
                    SELECT jsonb_array_elements_text(metadata->'add_words') AS word
                    FROM category_vectors
                    WHERE metadata->'add_words' IS NOT NULL
                ) sub
                WHERE word ILIKE %s
                ORDER BY word
                LIMIT %s
            """, (f"%{q}%", limit))
            words = [r["word"] for r in cur.fetchall()]
    finally:
        conn.close()
    return {"suggestions": words}


def _build_jsonb_filter(filters: dict | None) -> tuple[str, tuple]:
    if not filters:
        return "", ()
    clauses = []
    params = []
    for key, value in filters.items():
        clauses.append("AND metadata @> %s::jsonb")
        params.append(json.dumps({key: value}))
    return " ".join(clauses), tuple(params)


@router.post("/search/category", response_model=CategorySearchResponse)
def search_category(req: CategorySearchRequest) -> CategorySearchResponse:
    extra_where, extra_params = _build_jsonb_filter(req.filters)
    raw = search_table(
        table="category_vectors",
        query=req.query,
        limit=req.limit,
        offset=req.offset,
        lang_override=req.language,
        extra_where=extra_where,
        extra_params=extra_params,
        rerank=req.rerank,
    )

    results = [
        CategoryResult(
            category_id=r["category_id"],
            language=r["language"],
            narrative=r["narrative"],
            metadata=r["metadata"],
            rrf_score=r["rrf_score"],
            cosine_similarity=r.get("cosine_similarity"),
            reranked_score=r.get("reranked_score"),
        )
        for r in raw["results"]
    ]

    log_search_analytics(req.query, "category", raw["detected_language"], len(results), raw["response_time_ms"])
    logger.info(
        f"EVIDENCE_API_SEARCH_CATEGORY: query={req.query!r} "
        f"lang={raw['detected_language']} results={len(results)} "
        f"retrieval_mode={raw['retrieval_mode']}"
    )

    return CategorySearchResponse(
        detected_language=raw["detected_language"],
        response_time_ms=raw["response_time_ms"],
        retrieval_mode=raw["retrieval_mode"],
        results=results,
        total_count=raw["total_count"],
        offset=raw["offset"],
        cross_language_fallback_triggered=raw["cross_language_fallback_triggered"],
    )
