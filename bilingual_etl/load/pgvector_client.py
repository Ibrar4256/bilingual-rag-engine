"""
pgvector Client — Atomic Swap (R11)

Loads category/company vector rows into Postgres using a transactional
DELETE+INSERT ("atomic swap"): every update to a category's or company's
rows happens inside ONE database transaction, so a crash or error mid-update
leaves the OLD rows completely intact rather than partially deleted.

Without this, a naive "DELETE old rows, then INSERT new rows" as two
separately committed steps could crash in between the two — leaving that
category/company with ZERO rows in search until the next successful run.
Wrapping both in a transaction makes the whole update all-or-nothing.

Each row's `language` determines which of bm25_tokens_hu/bm25_tokens_en gets
populated — the other stays NULL (Postgres's to_tsvector() propagates a NULL
input straight to a NULL output, so passing None needs no special-casing).

pgvector's VECTOR type has no native psycopg2 adapter registered here, so
embeddings are passed as a Postgres array-literal string ("[0.1,0.2,...]")
and cast with `::vector` in the SQL itself — the standard technique for
drivers without the (optional) `pgvector` Python package installed.

Usage:
    upsert_category_vectors(conn, category_id, rows)
    upsert_company_vectors(conn, company_id, rows)
"""

from loguru import logger
from psycopg2.extras import Json


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def upsert_category_vectors(conn, category_id: str, rows: list[dict]) -> None:
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM category_vectors WHERE category_id = %s", (category_id,))
            for row in rows:
                bm25_hu = row["bm25_tokens"] if row["language"] == "hu" else None
                bm25_en = row["bm25_tokens"] if row["language"] == "en" else None
                cur.execute(
                    """
                    INSERT INTO category_vectors
                        (category_id, language, narrative, embedding,
                         bm25_tokens_hu, bm25_tokens_en, metadata, content_hash)
                    VALUES (%s, %s, %s, %s::vector,
                            to_tsvector('simple', %s), to_tsvector('simple', %s), %s, %s)
                    """,
                    (
                        category_id,
                        row["language"],
                        row["narrative"],
                        _format_vector(row["embedding"]),
                        bm25_hu,
                        bm25_en,
                        Json(row.get("metadata", {})),
                        row["content_hash"],
                    ),
                )
    logger.info(f"Upserted {len(rows)} category_vectors row(s) for category_id={category_id}")


def upsert_company_vectors(conn, company_id: str, rows: list[dict]) -> None:
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM company_vectors WHERE company_id = %s", (company_id,))
            for row in rows:
                bm25_hu = row["bm25_tokens"] if row["language"] == "hu" else None
                bm25_en = row["bm25_tokens"] if row["language"] == "en" else None
                cur.execute(
                    """
                    INSERT INTO company_vectors
                        (company_id, language, chunk_index, content_chunk, embedding,
                         bm25_tokens_hu, bm25_tokens_en, metadata, is_highlighted, content_hash)
                    VALUES (%s, %s, %s, %s, %s::vector,
                            to_tsvector('simple', %s), to_tsvector('simple', %s), %s, %s, %s)
                    """,
                    (
                        company_id,
                        row["language"],
                        row["chunk_index"],
                        row["content_chunk"],
                        _format_vector(row["embedding"]),
                        bm25_hu,
                        bm25_en,
                        Json(row.get("metadata", {})),
                        row.get("is_highlighted", False),
                        row["content_hash"],
                    ),
                )
    logger.info(f"Upserted {len(rows)} company_vectors row(s) for company_id={company_id}")


def get_category_content_hash(conn, category_id: str, language: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_hash FROM category_vectors WHERE category_id = %s AND language = %s",
            (category_id, language),
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_company_content_hash(conn, company_id: str, language: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_hash FROM company_vectors WHERE company_id = %s AND language = %s LIMIT 1",
            (company_id, language),
        )
        row = cur.fetchone()
        return row[0] if row else None
