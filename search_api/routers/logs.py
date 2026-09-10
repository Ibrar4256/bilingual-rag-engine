"""
GET /admin/logs — Recent application logs (admin only).
"""

from fastapi import APIRouter, Depends, Query

from search_api.routers.auth import require_admin
from search_api.services.log_buffer import get_recent_logs

router = APIRouter()


@router.get("/admin/logs", dependencies=[Depends(require_admin)])
def get_logs(
    limit: int = Query(100, ge=1, le=500),
    level: str | None = Query(None, description="Filter by level: DEBUG, INFO, WARNING, ERROR"),
    search: str | None = Query(None, max_length=200, description="Filter by text in message"),
):
    return get_recent_logs(limit=limit, level=level, search=search)
