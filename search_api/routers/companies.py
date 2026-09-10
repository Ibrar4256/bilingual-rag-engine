"""
POST /match/companies (R16) + POST /search/single-company (R17)

R16 — RFQ-to-supplier matching: JSONB pre-filters on metadata fields,
Partner Boost ×1.15 for is_highlighted companies, aggregates best chunk
per company.

R17 — Whitelabel search scoped to one company_id. Filter is applied
BEFORE the vector/BM25 search (WHERE company_id = X), not as a post-filter
(see .claude/rules/api-conventions.md). Partner Boost does NOT apply here.
"""

import time

from fastapi import APIRouter
from loguru import logger
from psycopg2.extras import RealDictCursor

from bilingual_etl.providers.embedding_provider import get_embedding_provider
from search_api.db import get_connection
from search_api.models.requests import CompanyMatchRequest, SingleCompanySearchRequest
from search_api.models.responses import (
    CompanyMatchResponse,
    CompanyResult,
    SingleCompanySearchResponse,
)
from search_api.services.search import log_search_analytics
from search_api.services.language_router import (
    bm25_column,
    detect_query_language,
    other_language,
    should_fallback,
)
from search_api.services.rrf import fuse_rankings

router = APIRouter()

PARTNER_BOOST = 1.15


def _build_jsonb_filter(filters: dict | None) -> tuple[str, tuple]:
    if not filters:
        return "", ()
    clauses = []
    params = []
    for key, value in filters.items():
        clauses.append("AND metadata @> %s::jsonb")
        import json
        params.append(json.dumps({key: value}))
    return " ".join(clauses), tuple(params)


def _format_vec(vec: list[float]) -> str:
    return "[" + ",".join(str(v) for v in vec) + "]"


@router.post("/match/companies", response_model=CompanyMatchResponse)
def match_companies(req: CompanyMatchRequest) -> CompanyMatchResponse:
    start = time.perf_counter()
    detected_lang = req.language or detect_query_language(req.query)
    extra_where, extra_params = _build_jsonb_filter(req.filters)

    provider = get_embedding_provider()
    query_vec = provider.embed_single(req.query)
    vec_literal = _format_vec(query_vec)

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            bm25_col = bm25_column(detected_lang)
            ts_config = "hungarian" if detected_lang == "hu" else "english"

            cur.execute(
                f"""
                SELECT company_id, language, chunk_index,
                       1 - (embedding <=> %s::vector) AS cosine_similarity
                FROM company_vectors
                WHERE language = %s {extra_where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_literal, detected_lang) + extra_params + (vec_literal, req.limit * 3),
            )
            vector_rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT company_id, language, chunk_index,
                       ts_rank({bm25_col}, plainto_tsquery(%s, %s)) AS bm25_rank_score
                FROM company_vectors
                WHERE {bm25_col} @@ plainto_tsquery(%s, %s)
                  AND language = %s {extra_where}
                ORDER BY ts_rank({bm25_col}, plainto_tsquery(%s, %s)) DESC
                LIMIT %s
                """,
                (ts_config, req.query, ts_config, req.query, detected_lang)
                + extra_params
                + (ts_config, req.query, req.limit * 3),
            )
            bm25_primary_rows = cur.fetchall()

            chunk_key = lambda r: f"{r['company_id']}:{r['chunk_index']}"
            vector_ids = [chunk_key(r) for r in vector_rows]
            bm25_primary_ids = [chunk_key(r) for r in bm25_primary_rows]

            bm25_secondary_ids = []
            sec_lang = other_language(detected_lang)
            if should_fallback([dict(r) for r in bm25_primary_rows]):
                sec_col = bm25_column(sec_lang)
                cur.execute(
                    f"""
                    SELECT company_id, language, chunk_index,
                           ts_rank({sec_col}, plainto_tsquery(%s, %s)) AS bm25_rank_score
                    FROM company_vectors
                    WHERE {sec_col} @@ plainto_tsquery(%s, %s)
                      AND language = %s {extra_where}
                    ORDER BY ts_rank({sec_col}, plainto_tsquery(%s, %s)) DESC
                    LIMIT %s
                    """,
                    (
                        "hungarian" if sec_lang == "hu" else "english", req.query,
                        "hungarian" if sec_lang == "hu" else "english", req.query,
                        sec_lang,
                    ) + extra_params + (
                        "hungarian" if sec_lang == "hu" else "english", req.query,
                        req.limit * 3,
                    ),
                )
                bm25_secondary_ids = [chunk_key(r) for r in cur.fetchall()]

            fused = fuse_rankings(vector_ids, bm25_primary_ids, bm25_secondary_ids)

            fused_chunk_keys = [ck for ck, _ in fused]
            total_count = 0
            if not fused_chunk_keys:
                results_out = []
            else:
                cid_set = list({ck.split(":")[0] for ck in fused_chunk_keys})
                ph = ",".join(["%s"] * len(cid_set))
                cur.execute(
                    f"SELECT * FROM company_vectors WHERE company_id IN ({ph})",
                    tuple(cid_set),
                )
                all_rows = {f"{r['company_id']}:{r['chunk_index']}:{r['language']}": dict(r) for r in cur.fetchall()}

                best_per_company: dict[str, tuple[float, dict]] = {}
                for ck, score in fused:
                    cid, cidx = ck.split(":")
                    row = all_rows.get(f"{cid}:{cidx}:{detected_lang}") or all_rows.get(f"{cid}:{cidx}:{sec_lang}")
                    if not row:
                        continue

                    effective_score = score * PARTNER_BOOST if row.get("is_highlighted") else score

                    if cid not in best_per_company or effective_score > best_per_company[cid][0]:
                        best_per_company[cid] = (effective_score, row)

                sorted_companies = sorted(best_per_company.values(), key=lambda x: x[0], reverse=True)
                total_count = len(sorted_companies)
                page = sorted_companies[req.offset:req.offset + req.limit]
                results_out = []
                for eff_score, row in page:
                    if "embedding" in row:
                        del row["embedding"]
                    results_out.append(
                        CompanyResult(
                            company_id=row["company_id"],
                            language=row["language"],
                            content_chunk=row["content_chunk"],
                            chunk_index=row["chunk_index"],
                            metadata=row["metadata"],
                            is_highlighted=row["is_highlighted"],
                            rrf_score=eff_score,
                        )
                    )
    finally:
        conn.close()

    elapsed = (time.perf_counter() - start) * 1000

    log_search_analytics(req.query, "companies", detected_lang, len(results_out), elapsed)
    logger.info(
        f"EVIDENCE_API_MATCH_COMPANIES: query={req.query!r} "
        f"lang={detected_lang} results={len(results_out)} "
        f"retrieval_mode=hybrid_rrf"
    )

    return CompanyMatchResponse(
        detected_language=detected_lang,
        response_time_ms=elapsed,
        results=results_out,
        total_count=total_count,
        offset=req.offset,
        cross_language_fallback_triggered=len(bm25_secondary_ids) > 0,
    )


@router.post("/search/single-company", response_model=SingleCompanySearchResponse)
def search_single_company(req: SingleCompanySearchRequest) -> SingleCompanySearchResponse:
    start = time.perf_counter()
    detected_lang = req.language or detect_query_language(req.query)
    scope_where = "AND company_id = %s"
    scope_params = (req.company_id,)

    provider = get_embedding_provider()
    query_vec = provider.embed_single(req.query)
    vec_literal = _format_vec(query_vec)

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            bm25_col = bm25_column(detected_lang)
            ts_config = "hungarian" if detected_lang == "hu" else "english"

            cur.execute(
                f"""
                SELECT company_id, language, chunk_index,
                       1 - (embedding <=> %s::vector) AS cosine_similarity
                FROM company_vectors
                WHERE language = %s {scope_where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_literal, detected_lang) + scope_params + (vec_literal, req.limit),
            )
            vector_rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT company_id, language, chunk_index,
                       ts_rank({bm25_col}, plainto_tsquery(%s, %s)) AS bm25_rank_score
                FROM company_vectors
                WHERE {bm25_col} @@ plainto_tsquery(%s, %s)
                  AND language = %s {scope_where}
                ORDER BY ts_rank({bm25_col}, plainto_tsquery(%s, %s)) DESC
                LIMIT %s
                """,
                (ts_config, req.query, ts_config, req.query, detected_lang)
                + scope_params
                + (ts_config, req.query, req.limit),
            )
            bm25_primary_rows = cur.fetchall()

            chunk_key = lambda r: f"{r['company_id']}:{r['chunk_index']}"
            vector_ids = [chunk_key(r) for r in vector_rows]
            bm25_primary_ids = [chunk_key(r) for r in bm25_primary_rows]

            bm25_secondary_ids = []
            sec_lang = other_language(detected_lang)
            if should_fallback([dict(r) for r in bm25_primary_rows]):
                sec_col = bm25_column(sec_lang)
                cur.execute(
                    f"""
                    SELECT company_id, language, chunk_index,
                           ts_rank({sec_col}, plainto_tsquery(%s, %s)) AS bm25_rank_score
                    FROM company_vectors
                    WHERE {sec_col} @@ plainto_tsquery(%s, %s)
                      AND language = %s {scope_where}
                    ORDER BY ts_rank({sec_col}, plainto_tsquery(%s, %s)) DESC
                    LIMIT %s
                    """,
                    (
                        "hungarian" if sec_lang == "hu" else "english", req.query,
                        "hungarian" if sec_lang == "hu" else "english", req.query,
                        sec_lang,
                    ) + scope_params + (
                        "hungarian" if sec_lang == "hu" else "english", req.query,
                        req.limit,
                    ),
                )
                bm25_secondary_ids = [chunk_key(r) for r in cur.fetchall()]

            fused = fuse_rankings(vector_ids, bm25_primary_ids, bm25_secondary_ids)
            total_count_single = len(fused)
            page_single = fused[req.offset:req.offset + req.limit]

            results_out = []
            fused_keys = [ck for ck, _ in page_single]
            if fused_keys:
                cur.execute(
                    f"SELECT * FROM company_vectors WHERE company_id = %s",
                    (req.company_id,),
                )
                all_rows = {f"{r['chunk_index']}:{r['language']}": dict(r) for r in cur.fetchall()}

                for ck, score in page_single:
                    _, cidx = ck.split(":")
                    row = all_rows.get(f"{cidx}:{detected_lang}") or all_rows.get(f"{cidx}:{sec_lang}")
                    if not row:
                        continue
                    if "embedding" in row:
                        del row["embedding"]
                    results_out.append(
                        CompanyResult(
                            company_id=row["company_id"],
                            language=row["language"],
                            content_chunk=row["content_chunk"],
                            chunk_index=row["chunk_index"],
                            metadata=row["metadata"],
                            is_highlighted=row["is_highlighted"],
                            rrf_score=score,
                        )
                    )
    finally:
        conn.close()

    elapsed = (time.perf_counter() - start) * 1000

    log_search_analytics(req.query, "single_company", detected_lang, len(results_out), elapsed)
    logger.info(
        f"EVIDENCE_API_SINGLE_COMPANY: company_id={req.company_id} query={req.query!r} "
        f"lang={detected_lang} results={len(results_out)} "
        f"retrieval_mode=hybrid_rrf"
    )

    return SingleCompanySearchResponse(
        company_id=req.company_id,
        detected_language=detected_lang,
        response_time_ms=elapsed,
        results=results_out,
        total_count=total_count_single,
        offset=req.offset,
        cross_language_fallback_triggered=len(bm25_secondary_ids) > 0,
    )
