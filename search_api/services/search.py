"""
Shared search logic for all endpoints (R13, R14, R15, R16, R17, R19)

Every search endpoint follows the same three-step process:
  1. Embed the query text → vector
  2. Run parallel vector + BM25 searches against the target table
  3. Fuse results with RRF (+ cross-language fallback if needed)

This module encapsulates steps 1–3 so the routers stay thin.
"""

import time
from typing import Literal

from loguru import logger
from psycopg2.extras import RealDictCursor

from bilingual_etl.providers.embedding_provider import get_embedding_provider
from search_api.db import get_connection

_ANALYTICS_TABLE_ENSURED = False


def _ensure_analytics_table(conn) -> None:
    global _ANALYTICS_TABLE_ENSURED
    if _ANALYTICS_TABLE_ENSURED:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS search_analytics (
                    id SERIAL PRIMARY KEY,
                    query TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    language TEXT,
                    result_count INT,
                    response_time_ms FLOAT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
        _ANALYTICS_TABLE_ENSURED = True
    except Exception:
        pass


def log_search_analytics(query: str, endpoint: str, language: str, result_count: int, response_time_ms: float) -> None:
    try:
        conn = get_connection()
        try:
            _ensure_analytics_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO search_analytics (query, endpoint, language, result_count, response_time_ms) VALUES (%s, %s, %s, %s, %s)",
                    (query, endpoint, language, result_count, response_time_ms),
                )
                conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
from search_api.services.language_router import (
    bm25_column,
    detect_query_language,
    other_language,
    should_fallback,
)
from search_api.services.rrf import fuse_rankings


def embed_query(query: str) -> list[float]:
    provider = get_embedding_provider()
    return provider.embed_single(query)


def _format_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(v) for v in vec) + "]"


def _vector_search(
    cur,
    table: str,
    query_vec: list[float],
    lang: str,
    limit: int,
    id_col: str,
    extra_where: str = "",
    extra_params: tuple = (),
) -> list[dict]:
    vec_literal = _format_vector_literal(query_vec)
    sql = f"""
        SELECT {id_col}, language,
               1 - (embedding <=> %s::vector) AS cosine_similarity
        FROM {table}
        WHERE language = %s {extra_where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(sql, (vec_literal, lang) + extra_params + (vec_literal, limit))
    return cur.fetchall()


def _bm25_search(
    cur,
    table: str,
    query: str,
    lang: str,
    limit: int,
    id_col: str,
    extra_where: str = "",
    extra_params: tuple = (),
) -> list[dict]:
    col = bm25_column(lang)
    ts_query_config = "hungarian" if lang == "hu" else "english"
    sql = f"""
        SELECT {id_col}, language,
               ts_rank({col}, plainto_tsquery(%s, %s)) AS bm25_rank_score
        FROM {table}
        WHERE {col} @@ plainto_tsquery(%s, %s) {extra_where}
        ORDER BY ts_rank({col}, plainto_tsquery(%s, %s)) DESC
        LIMIT %s
    """
    params = (ts_query_config, query, ts_query_config, query) + extra_params + (ts_query_config, query, limit)
    cur.execute(sql, params)
    return cur.fetchall()


def _parse_pg_vector(emb) -> list[float] | None:
    if isinstance(emb, (list, tuple)):
        return list(emb)
    if isinstance(emb, str):
        s = emb.strip("[] ")
        if s:
            return [float(x) for x in s.split(",")]
    return None


def _rerank_by_cosine(results: list[dict], query_vec: list[float], weight: float = 0.3) -> list[dict]:
    if not results or not query_vec:
        return results
    import numpy as np
    q = np.array(query_vec, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return results
    q = q / q_norm

    for r in results:
        emb = _parse_pg_vector(r.get("_embedding"))
        if emb is not None:
            d = np.array(emb, dtype=np.float32)
            d_norm = np.linalg.norm(d)
            cos_sim = float(np.dot(q, d) / d_norm) if d_norm > 0 else 0.0
        else:
            cos_sim = 0.0
        rrf = r.get("rrf_score", 0.0)
        r["cosine_similarity"] = round(cos_sim, 5)
        r["reranked_score"] = round((1 - weight) * rrf + weight * cos_sim, 5)

    results.sort(key=lambda r: r["reranked_score"], reverse=True)
    return results


def search_table(
    table: Literal["category_vectors", "company_vectors"],
    query: str,
    limit: int = 20,
    offset: int = 0,
    lang_override: str | None = None,
    extra_where: str = "",
    extra_params: tuple = (),
    rerank: bool = False,
) -> dict:
    start = time.perf_counter()
    id_col = "category_id" if table == "category_vectors" else "company_id"
    detected_lang = lang_override or detect_query_language(query)

    fetch_limit = offset + limit + 10
    query_vec = embed_query(query)

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            vector_rows = _vector_search(
                cur, table, query_vec, detected_lang, fetch_limit, id_col,
                extra_where, extra_params,
            )
            bm25_primary_rows = _bm25_search(
                cur, table, query, detected_lang, fetch_limit, id_col,
                extra_where, extra_params,
            )

            vector_ids = [r[id_col] for r in vector_rows]
            bm25_primary_ids = [r[id_col] for r in bm25_primary_rows]

            bm25_secondary_ids = []
            secondary_lang = other_language(detected_lang)
            bm25_primary_dicts = [dict(r) for r in bm25_primary_rows]
            if should_fallback(bm25_primary_dicts):
                bm25_secondary_rows = _bm25_search(
                    cur, table, query, secondary_lang, fetch_limit, id_col,
                    extra_where, extra_params,
                )
                bm25_secondary_ids = [r[id_col] for r in bm25_secondary_rows]

            fused = fuse_rankings(vector_ids, bm25_primary_ids, bm25_secondary_ids)
            total_count = len(fused)
            page = fused[offset:offset + limit]
            fused_ids = [item_id for item_id, _ in page]

            if not fused_ids:
                results = []
            else:
                placeholders = ",".join(["%s"] * len(fused_ids))
                fetch_sql = f"SELECT * FROM {table} WHERE {id_col} IN ({placeholders}) AND language = %s"
                cur.execute(fetch_sql, tuple(fused_ids) + (detected_lang,))
                rows_by_id = {r[id_col]: dict(r) for r in cur.fetchall()}

                if not rows_by_id and bm25_secondary_ids:
                    cur.execute(fetch_sql, tuple(fused_ids) + (secondary_lang,))
                    rows_by_id = {r[id_col]: dict(r) for r in cur.fetchall()}

                results = []
                for item_id, score in page:
                    row = rows_by_id.get(item_id)
                    if row:
                        row["rrf_score"] = score
                        if rerank and "embedding" in row:
                            row["_embedding"] = row.pop("embedding")
                        elif "embedding" in row:
                            del row["embedding"]
                        results.append(row)
    finally:
        conn.close()

    retrieval_mode = "hybrid_rrf"
    if rerank and results:
        results = _rerank_by_cosine(results, query_vec)
        retrieval_mode = "hybrid_rrf_reranked"
    for r in results:
        r.pop("_embedding", None)

    elapsed = (time.perf_counter() - start) * 1000
    return {
        "detected_language": detected_lang,
        "response_time_ms": elapsed,
        "retrieval_mode": retrieval_mode,
        "results": results,
        "total_count": total_count,
        "offset": offset,
        "cross_language_fallback_triggered": len(bm25_secondary_ids) > 0,
    }
