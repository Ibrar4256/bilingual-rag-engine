"""
RAG (Retrieval-Augmented Generation) service.

Retrieves relevant documents via hybrid search, builds a context window,
and generates an LLM answer with citations back to source documents.

Supports both synchronous (POST /ask) and streaming (POST /ask with stream=true)
responses. The streaming path yields SSE events: metadata first, then answer
tokens in chunks, then a done event.
"""

import json
import time
from collections.abc import Generator

from loguru import logger

from bilingual_etl.providers.llm_provider import get_llm_provider, generate_with_retry
from search_api.services.search import search_table, log_search_analytics


RAG_SYSTEM_PROMPT = (
    "You are a helpful B2B search assistant for a Hungarian industrial marketplace. "
    "Answer the user's question using ONLY the context documents provided below. "
    "If the context does not contain enough information, say so — do not make up facts.\n\n"
    "Rules:\n"
    "- Cite sources using [1], [2], etc. matching the document numbers in the context.\n"
    "- If the question is in Hungarian, answer in Hungarian. If in English, answer in English.\n"
    "- Be concise but thorough. Use bullet points for lists.\n"
    "- Include specific details (company names, category names, technical specs) from the context."
)

MAX_CONTEXT_CHARS = 8000


def _build_context(results: list[dict], table: str) -> tuple[str, list[dict]]:
    """Build a numbered context string from search results. Returns (context_text, citations)."""
    is_category = table == "category_vectors"
    citations = []
    context_parts = []
    char_count = 0

    for i, r in enumerate(results, 1):
        if is_category:
            doc_id = r.get("category_id", "?")
            text = r.get("narrative", "")
            label = f"Category #{doc_id}"
        else:
            doc_id = r.get("company_id", "?")
            text = r.get("content_chunk", "")
            label = f"Company #{doc_id}"

        if char_count + len(text) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - char_count
            if remaining > 200:
                text = text[:remaining] + "..."
            else:
                break

        block = f"[{i}] {label} (lang={r.get('language', '?')}, score={r.get('rrf_score', 0):.4f}):\n{text}"
        context_parts.append(block)
        char_count += len(text)

        citations.append({
            "ref": i,
            "id": str(doc_id),
            "type": "category" if is_category else "company",
            "language": r.get("language", ""),
            "rrf_score": r.get("rrf_score", 0),
        })

    return "\n\n".join(context_parts), citations


def rag_answer(
    query: str,
    table: str = "category_vectors",
    limit: int = 5,
    lang_override: str | None = None,
) -> dict:
    start = time.perf_counter()

    raw = search_table(
        table=table,
        query=query,
        limit=limit,
        lang_override=lang_override,
        rerank=True,
    )

    results = raw["results"]
    if not results:
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "answer": "No relevant documents found for your query. Try rephrasing or using different keywords.",
            "citations": [],
            "detected_language": raw["detected_language"],
            "retrieval_mode": raw["retrieval_mode"],
            "results_used": 0,
            "response_time_ms": elapsed,
        }

    context_text, citations = _build_context(results, table)

    user_prompt = (
        f"Context documents:\n\n{context_text}\n\n"
        f"---\n"
        f"Question: {query}\n\n"
        f"Answer the question using the context above. Cite sources with [1], [2], etc."
    )

    llm = get_llm_provider()
    logger.info(f"RAG: generating answer with provider={llm.name} for query={query!r}")
    answer = generate_with_retry(llm, user_prompt, system_prompt=RAG_SYSTEM_PROMPT)

    from bilingual_etl.providers.guardrails import validate_rag_answer
    guardrail_warnings = validate_rag_answer(answer, citations)

    elapsed = (time.perf_counter() - start) * 1000

    log_search_analytics(query, "rag", raw["detected_language"], len(results), elapsed)

    return {
        "answer": answer,
        "citations": citations,
        "detected_language": raw["detected_language"],
        "retrieval_mode": raw["retrieval_mode"],
        "results_used": len(citations),
        "response_time_ms": elapsed,
        "guardrail_warnings": guardrail_warnings,
    }


STREAM_CHUNK_SIZE = 4


def rag_answer_stream(
    query: str,
    table: str = "category_vectors",
    limit: int = 5,
    lang_override: str | None = None,
) -> Generator[str, None, None]:
    """Yield SSE events for a RAG answer: metadata, token chunks, done."""
    start = time.perf_counter()

    raw = search_table(
        table=table, query=query, limit=limit,
        lang_override=lang_override, rerank=True,
    )

    results = raw["results"]
    if not results:
        elapsed = (time.perf_counter() - start) * 1000
        yield _sse_event("metadata", {
            "citations": [],
            "detected_language": raw["detected_language"],
            "retrieval_mode": raw["retrieval_mode"],
            "results_used": 0,
        })
        yield _sse_event("token", {"text": "No relevant documents found for your query."})
        yield _sse_event("done", {"response_time_ms": round(elapsed, 1)})
        return

    context_text, citations = _build_context(results, table)

    yield _sse_event("metadata", {
        "citations": citations,
        "detected_language": raw["detected_language"],
        "retrieval_mode": raw["retrieval_mode"],
        "results_used": len(citations),
    })

    user_prompt = (
        f"Context documents:\n\n{context_text}\n\n"
        f"---\n"
        f"Question: {query}\n\n"
        f"Answer the question using the context above. Cite sources with [1], [2], etc."
    )

    llm = get_llm_provider()
    logger.info(f"RAG SSE: generating answer with provider={llm.name}")
    answer = generate_with_retry(llm, user_prompt, system_prompt=RAG_SYSTEM_PROMPT)

    words = answer.split(" ")
    for i in range(0, len(words), STREAM_CHUNK_SIZE):
        chunk = " ".join(words[i:i + STREAM_CHUNK_SIZE])
        if i > 0:
            chunk = " " + chunk
        yield _sse_event("token", {"text": chunk})

    elapsed = (time.perf_counter() - start) * 1000
    log_search_analytics(query, "rag_stream", raw["detected_language"], len(results), elapsed)

    yield _sse_event("done", {"response_time_ms": round(elapsed, 1)})


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
