"""
POST /agent/ask — Search agent with tool-use pattern.

The agent plans which search tools to call, executes them,
and synthesizes results into a final answer.
"""

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from search_api.services.search_agent import run_search_agent

router = APIRouter()


class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language question")


@router.post("/agent/ask")
def agent_ask(req: AgentRequest):
    logger.info(f"EVIDENCE_AGENT_REQUEST: query={req.query!r}")
    return run_search_agent(req.query)
