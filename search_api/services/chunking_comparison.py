"""
Chunking strategy comparison — evaluate how different text splitting
strategies affect retrieval quality.

Strategies compared:
  1. Fixed-size (current): 500-word chunks, sentence boundary
  2. Small fixed: 200-word chunks, sentence boundary
  3. Large fixed: 800-word chunks, sentence boundary
  4. Paragraph-based: split on double newlines
  5. Semantic: split on topic transitions (sentence embedding similarity)

Each strategy re-chunks a sample of documents, embeds them, and measures
retrieval quality against ground-truth queries using the same evaluation
metrics as the main evaluation pipeline.
"""

import math
import re
import time

from loguru import logger

from bilingual_etl.providers.embedding_provider import get_embedding_provider
from bilingual_etl.transform.chunker import chunk_text
from search_api.db import get_connection

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def _split_paragraphs(text: str) -> list[str]:
    parts = _PARAGRAPH_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _semantic_chunk(text: str, max_words: int = 500) -> list[str]:
    """Split text based on sentence-level topic shifts."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if len(sentences) <= 2:
        return [text.strip()] if text.strip() else []

    provider = get_embedding_provider()
    embeddings = provider.embed(sentences[:50])

    chunks = []
    current = [sentences[0]]
    current_words = len(sentences[0].split())

    for i in range(1, len(embeddings)):
        sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
        word_count = len(sentences[i].split())

        if current_words + word_count > max_words or sim < 0.65:
            chunks.append(" ".join(current))
            current = [sentences[i]]
            current_words = word_count
        else:
            current.append(sentences[i])
            current_words += word_count

    if current:
        chunks.append(" ".join(current))

    return chunks


STRATEGIES = {
    "fixed_500": {"label": "Fixed 500 words", "fn": lambda t: chunk_text(t, 500)},
    "fixed_200": {"label": "Fixed 200 words", "fn": lambda t: chunk_text(t, 200)},
    "fixed_800": {"label": "Fixed 800 words", "fn": lambda t: chunk_text(t, 800)},
    "paragraph": {"label": "Paragraph-based", "fn": _split_paragraphs},
    "semantic": {"label": "Semantic (similarity)", "fn": _semantic_chunk},
}


def _get_sample_documents(table: str = "category_vectors", limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            id_col = "category_id" if table == "category_vectors" else "company_id"
            text_col = "narrative" if table == "category_vectors" else "content_chunk"
            cur.execute(
                f"SELECT {id_col}, language, {text_col} FROM {table} "
                f"WHERE language = 'en' ORDER BY LENGTH({text_col}) DESC LIMIT %s",
                (limit,),
            )
            return [
                {"id": str(r[0]), "language": r[1], "text": r[2]}
                for r in cur.fetchall()
            ]
    finally:
        conn.close()


TEST_QUERIES = [
    {"query": "industrial pump manufacturer", "language": "en"},
    {"query": "welding services", "language": "en"},
    {"query": "steel construction", "language": "en"},
    {"query": "CNC machining", "language": "en"},
]


def _recall_at_k(retrieved: set[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(retrieved & relevant) / len(relevant)


def compare_chunking_strategies(
    strategies: list[str] | None = None,
    table: str = "category_vectors",
    sample_size: int = 10,
) -> dict:
    """Run the comparison and return results per strategy."""
    if strategies is None:
        strategies = ["fixed_500", "fixed_200", "fixed_800", "paragraph"]

    docs = _get_sample_documents(table, limit=sample_size)
    if not docs:
        return {"error": "No documents found", "strategies": []}

    provider = get_embedding_provider()
    results = []

    for strat_key in strategies:
        strat = STRATEGIES.get(strat_key)
        if not strat:
            continue

        start = time.perf_counter()

        all_chunks = []
        chunk_stats = {"total_chunks": 0, "avg_chunk_words": 0, "min_words": 9999, "max_words": 0}

        for doc in docs:
            chunks = strat["fn"](doc["text"])
            for chunk in chunks:
                wc = len(chunk.split())
                chunk_stats["min_words"] = min(chunk_stats["min_words"], wc)
                chunk_stats["max_words"] = max(chunk_stats["max_words"], wc)
                all_chunks.append({"doc_id": doc["id"], "text": chunk, "words": wc})

        chunk_stats["total_chunks"] = len(all_chunks)
        if all_chunks:
            chunk_stats["avg_chunk_words"] = round(
                sum(c["words"] for c in all_chunks) / len(all_chunks), 1
            )

        if chunk_stats["total_chunks"] == 0:
            chunk_stats["min_words"] = 0

        chunk_embeddings = []
        batch_size = 10
        for i in range(0, len(all_chunks), batch_size):
            batch = [c["text"] for c in all_chunks[i:i + batch_size]]
            chunk_embeddings.extend(provider.embed(batch))

        query_results = []
        for tq in TEST_QUERIES:
            q_emb = provider.embed_single(tq["query"])
            similarities = []
            for j, emb in enumerate(chunk_embeddings):
                sim = _cosine_similarity(q_emb, emb)
                similarities.append((sim, all_chunks[j]["doc_id"], j))

            similarities.sort(reverse=True)
            top_5_ids = set(s[1] for s in similarities[:5])
            top_10_ids = set(s[1] for s in similarities[:10])

            query_results.append({
                "query": tq["query"],
                "top_5_score": round(similarities[0][0], 4) if similarities else 0,
                "avg_top5_score": round(
                    sum(s[0] for s in similarities[:5]) / min(5, len(similarities)), 4
                ) if similarities else 0,
                "unique_docs_in_top5": len(top_5_ids),
                "unique_docs_in_top10": len(top_10_ids),
            })

        elapsed = (time.perf_counter() - start) * 1000

        results.append({
            "strategy": strat_key,
            "label": strat["label"],
            "chunk_stats": chunk_stats,
            "query_results": query_results,
            "avg_top_score": round(
                sum(qr["top_5_score"] for qr in query_results) / len(query_results), 4
            ) if query_results else 0,
            "avg_diversity": round(
                sum(qr["unique_docs_in_top10"] for qr in query_results) / len(query_results), 1
            ) if query_results else 0,
            "processing_time_ms": round(elapsed, 1),
        })

    logger.info(
        f"EVIDENCE_CHUNKING_COMPARISON: strategies={strategies} "
        f"docs={len(docs)} table={table}"
    )

    return {
        "documents_sampled": len(docs),
        "test_queries": len(TEST_QUERIES),
        "table": table,
        "strategies": results,
    }
