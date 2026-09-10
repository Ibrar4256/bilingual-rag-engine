"""
GET /admin/evaluation — Run search quality evaluation.

Compares vector-only, BM25-only, hybrid RRF, and hybrid+rerank
on a ground-truth test set. Returns MRR, NDCG@10, Recall@10.
"""

from fastapi import APIRouter, Depends, Query
from loguru import logger

from search_api.routers.auth import require_admin
from search_api.services.evaluation import run_evaluation

router = APIRouter()


@router.get("/admin/evaluation", dependencies=[Depends(require_admin)])
def get_evaluation(k: int = Query(10, ge=1, le=50)):
    logger.info(f"EVIDENCE_EVALUATION_RUN: k={k}")
    return run_evaluation(k=k)
