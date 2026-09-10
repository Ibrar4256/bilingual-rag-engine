"""
GET /admin/observability — LLM call traces and token usage dashboard.

Returns aggregated stats: total calls, tokens, cost, latency by provider,
plus recent trace log.
"""

from fastapi import APIRouter, Depends, Query
from loguru import logger

from search_api.routers.auth import require_admin
from search_api.services.llm_traces import get_observability_stats

router = APIRouter()


@router.get("/admin/observability", dependencies=[Depends(require_admin)])
def get_observability(hours: int = Query(24, ge=1, le=720)):
    logger.info(f"EVIDENCE_OBSERVABILITY_QUERY: hours={hours}")
    return get_observability_stats(hours=hours)
