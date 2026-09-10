"""
POST /ask — RAG (Retrieval-Augmented Generation) endpoint.

Retrieves relevant documents via hybrid search, feeds them as context
to the LLM, and returns a generated answer with citations.

Supports both JSON response (default) and SSE streaming (stream=true).
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from loguru import logger

from search_api.models.requests import RAGRequest
from search_api.models.responses import RAGResponse, RAGCitation
from search_api.services.rag import rag_answer, rag_answer_stream

router = APIRouter()


@router.post("/ask")
def ask(req: RAGRequest):
    if req.stream:
        logger.info(f"EVIDENCE_RAG_STREAM: query={req.query!r} stream=true")
        return StreamingResponse(
            rag_answer_stream(
                query=req.query,
                table=req.table,
                limit=req.limit,
                lang_override=req.language,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = rag_answer(
        query=req.query,
        table=req.table,
        limit=req.limit,
        lang_override=req.language,
    )

    logger.info(
        f"EVIDENCE_RAG_ANSWER: query={req.query!r} "
        f"lang={result['detected_language']} citations={result['results_used']} "
        f"time_ms={result['response_time_ms']:.0f}"
    )

    return RAGResponse(
        answer=result["answer"],
        citations=[RAGCitation(**c) for c in result["citations"]],
        detected_language=result["detected_language"],
        retrieval_mode=result["retrieval_mode"],
        results_used=result["results_used"],
        response_time_ms=result["response_time_ms"],
    )
