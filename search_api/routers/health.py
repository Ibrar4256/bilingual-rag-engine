"""
GET /health (R18)

Verifies DB connectivity, the pgvector HNSW indexes, and the BM25 GIN
indexes exist. Reaching this handler at all proves API connectivity, so
that check has no separate field. Checks run independently — a missing
index degrades `status` to "degraded" instead of the whole endpoint 500ing,
since a partial index outage is still useful information for the caller.
"""

import time

from fastapi import APIRouter
from loguru import logger

from search_api.db import get_connection
from search_api.models.responses import HealthChecks, HealthResponse

router = APIRouter()

REQUIRED_INDEXES = {
    "idx_category_vectors_embedding",
    "idx_company_vectors_embedding",
    "idx_category_bm25_hu",
    "idx_category_bm25_en",
    "idx_company_bm25_hu",
    "idx_company_bm25_en",
}


def _check_indexes(conn) -> tuple[bool, bool]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE indexname = ANY(%s)",
            (list(REQUIRED_INDEXES),),
        )
        found = {row[0] for row in cur.fetchall()}

    vector_index = {"idx_category_vectors_embedding", "idx_company_vectors_embedding"} <= found
    bm25_index = {
        "idx_category_bm25_hu",
        "idx_category_bm25_en",
        "idx_company_bm25_hu",
        "idx_company_bm25_en",
    } <= found
    return vector_index, bm25_index


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    start = time.perf_counter()

    database = vector_index = bm25_index = False
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            database = True
            vector_index, bm25_index = _check_indexes(conn)
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"EVIDENCE_API_HEALTH_DB_UNREACHABLE: {e}")

    all_ok = database and vector_index and bm25_index
    response_time_ms = (time.perf_counter() - start) * 1000

    logger.info(
        f"EVIDENCE_API_HEALTH_CHECK: status={'ok' if all_ok else 'degraded'} "
        f"database={database} vector_index={vector_index} bm25_index={bm25_index}"
    )

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        checks=HealthChecks(database=database, vector_index=vector_index, bm25_index=bm25_index),
        response_time_ms=response_time_ms,
    )
