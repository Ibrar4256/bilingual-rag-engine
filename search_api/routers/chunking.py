"""
GET /admin/chunking-comparison — Compare chunking strategies.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from loguru import logger

from search_api.routers.auth import require_admin
from search_api.services.chunking_comparison import compare_chunking_strategies

router = APIRouter()


@router.get("/admin/chunking-comparison", dependencies=[Depends(require_admin)])
def get_chunking_comparison(
    sample_size: int = Query(10, ge=1, le=50),
    table: Literal["category_vectors", "company_vectors"] = Query("category_vectors"),
):
    logger.info(f"EVIDENCE_CHUNKING_COMPARISON_RUN: sample={sample_size} table={table}")
    return compare_chunking_strategies(
        strategies=["fixed_500", "fixed_200", "fixed_800", "paragraph"],
        table=table,
        sample_size=sample_size,
    )
