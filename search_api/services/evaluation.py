"""
Search quality evaluation — MRR, NDCG@10, Recall@k.

Compares retrieval modes: vector-only, BM25-only, hybrid RRF, hybrid+rerank.
Runs against a ground-truth test set of (query, relevant_ids) pairs.
"""

import math
import time

from loguru import logger
from psycopg2.extras import RealDictCursor

from bilingual_etl.providers.embedding_provider import get_embedding_provider
from search_api.db import get_connection
from search_api.services.language_router import bm25_column
from search_api.services.search import search_table


GROUND_TRUTH = [
    {
        "query": "ipari szivattyú",
        "language": "hu",
        "table": "category_vectors",
        "relevant_ids": ["905", "906", "907"],
        "description": "Industrial pumps (Hungarian)",
    },
    {
        "query": "industrial pump manufacturer",
        "language": "en",
        "table": "category_vectors",
        "relevant_ids": ["905", "906", "907"],
        "description": "Industrial pumps (English)",
    },
    {
        "query": "hegesztés",
        "language": "hu",
        "table": "category_vectors",
        "relevant_ids": ["910", "911"],
        "description": "Welding (Hungarian)",
    },
    {
        "query": "solar panel installation",
        "language": "en",
        "table": "category_vectors",
        "relevant_ids": ["920", "921"],
        "description": "Solar panels (English)",
    },
    {
        "query": "acél szerkezet gyártás",
        "language": "hu",
        "table": "category_vectors",
        "relevant_ids": ["912", "913", "914"],
        "description": "Steel structure manufacturing (Hungarian)",
    },
    {
        "query": "CNC machining precision",
        "language": "en",
        "table": "company_vectors",
        "relevant_ids": [],
        "description": "CNC machining companies (English) — IDs populated at runtime",
    },
]


def _reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for i, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_ids:
            return 1.0 / i
    return 0.0


def _dcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    dcg = 0.0
    for i, rid in enumerate(retrieved_ids[:k], 1):
        rel = 1.0 if rid in relevant_ids else 0.0
        dcg += rel / math.log2(i + 1)
    return dcg


def _ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    dcg = _dcg_at_k(retrieved_ids, relevant_ids, k)
    ideal_ids = [rid for rid in retrieved_ids if rid in relevant_ids]
    ideal_ids += ["dummy"] * max(0, len(relevant_ids) - len(ideal_ids))
    idcg = _dcg_at_k(ideal_ids[:k], relevant_ids, k)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def _recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    retrieved_set = set(retrieved_ids[:k])
    return len(retrieved_set & relevant_ids) / len(relevant_ids)


def _vector_only_search(query: str, table: str, lang: str, limit: int) -> list[str]:
    provider = get_embedding_provider()
    query_vec = provider.embed_single(query)
    vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"
    id_col = "category_id" if table == "category_vectors" else "company_id"

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = f"""
                SELECT {id_col}
                FROM {table}
                WHERE language = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            cur.execute(sql, (lang, vec_literal, limit))
            return [str(r[id_col]) for r in cur.fetchall()]
    finally:
        conn.close()


def _bm25_only_search(query: str, table: str, lang: str, limit: int) -> list[str]:
    col = bm25_column(lang)
    ts_config = "hungarian" if lang == "hu" else "english"
    id_col = "category_id" if table == "category_vectors" else "company_id"

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = f"""
                SELECT {id_col}
                FROM {table}
                WHERE {col} @@ plainto_tsquery(%s, %s)
                ORDER BY ts_rank({col}, plainto_tsquery(%s, %s)) DESC
                LIMIT %s
            """
            cur.execute(sql, (ts_config, query, ts_config, query, limit))
            return [str(r[id_col]) for r in cur.fetchall()]
    finally:
        conn.close()


def _hybrid_search(query: str, table: str, lang: str, limit: int, rerank: bool = False) -> list[str]:
    id_col = "category_id" if table == "category_vectors" else "company_id"
    raw = search_table(table=table, query=query, limit=limit, lang_override=lang, rerank=rerank)
    return [str(r[id_col]) for r in raw["results"]]


def evaluate_query(
    query: str,
    table: str,
    lang: str,
    relevant_ids: set[str],
    k: int = 10,
) -> dict:
    results = {}
    modes = {
        "vector_only": lambda: _vector_only_search(query, table, lang, k),
        "bm25_only": lambda: _bm25_only_search(query, table, lang, k),
        "hybrid_rrf": lambda: _hybrid_search(query, table, lang, k, rerank=False),
        "hybrid_reranked": lambda: _hybrid_search(query, table, lang, k, rerank=True),
    }

    for mode_name, search_fn in modes.items():
        start = time.perf_counter()
        try:
            retrieved = search_fn()
        except Exception as e:
            logger.warning(f"Eval {mode_name} failed for query={query!r}: {e}")
            retrieved = []
        elapsed = (time.perf_counter() - start) * 1000

        results[mode_name] = {
            "retrieved_ids": retrieved,
            "mrr": _reciprocal_rank(retrieved, relevant_ids),
            "ndcg@10": _ndcg_at_k(retrieved, relevant_ids, k),
            "recall@10": _recall_at_k(retrieved, relevant_ids, k),
            "latency_ms": round(elapsed, 1),
        }

    return results


def run_evaluation(k: int = 10) -> dict:
    test_cases = [tc for tc in GROUND_TRUTH if tc["relevant_ids"]]
    all_results = []

    for tc in test_cases:
        relevant = set(tc["relevant_ids"])
        query_results = evaluate_query(
            query=tc["query"],
            table=tc["table"],
            lang=tc["language"],
            relevant_ids=relevant,
            k=k,
        )
        all_results.append({
            "query": tc["query"],
            "description": tc["description"],
            "relevant_count": len(relevant),
            "modes": query_results,
        })

    modes = ["vector_only", "bm25_only", "hybrid_rrf", "hybrid_reranked"]
    summary = {}
    for mode in modes:
        mrrs = [r["modes"][mode]["mrr"] for r in all_results if mode in r["modes"]]
        ndcgs = [r["modes"][mode]["ndcg@10"] for r in all_results if mode in r["modes"]]
        recalls = [r["modes"][mode]["recall@10"] for r in all_results if mode in r["modes"]]
        latencies = [r["modes"][mode]["latency_ms"] for r in all_results if mode in r["modes"]]

        n = len(mrrs) or 1
        summary[mode] = {
            "avg_mrr": round(sum(mrrs) / n, 4),
            "avg_ndcg@10": round(sum(ndcgs) / n, 4),
            "avg_recall@10": round(sum(recalls) / n, 4),
            "avg_latency_ms": round(sum(latencies) / n, 1),
            "queries_evaluated": n,
        }

    return {
        "k": k,
        "test_cases": len(test_cases),
        "per_query": all_results,
        "summary": summary,
    }
