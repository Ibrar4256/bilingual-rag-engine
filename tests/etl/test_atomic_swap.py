"""
Tests for pgvector client + atomic swap (R11, AC-4).

These are integration tests against a real Postgres connection — mocking
psycopg2's transaction/rollback behavior would only prove our mock does what
we told it to, not that a real DELETE+INSERT actually rolls back atomically.
That guarantee can only be verified against a real database.

Requires the local dev Postgres container running (see docker-compose.yml).
Skips gracefully if it isn't reachable, rather than failing the whole suite.
"""

import psycopg2
import pytest

from bilingual_etl.load.db import get_connection
from bilingual_etl.load.pgvector_client import (
    get_category_content_hash,
    get_company_content_hash,
    upsert_category_vectors,
    upsert_company_vectors,
)

TEST_CATEGORY_ID = "TEST_ATOMIC_SWAP_CATEGORY"
TEST_COMPANY_ID = "TEST_ATOMIC_SWAP_COMPANY"

FAKE_VECTOR = [0.0] * 768


def _db_available() -> bool:
    try:
        conn = get_connection()
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable at DATABASE_URL")


@pytest.fixture
def conn():
    connection = get_connection()
    with connection.cursor() as cur:
        cur.execute("DELETE FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,))
        cur.execute("DELETE FROM company_vectors WHERE company_id = %s", (TEST_COMPANY_ID,))
    connection.commit()

    yield connection

    with connection.cursor() as cur:
        cur.execute("DELETE FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,))
        cur.execute("DELETE FROM company_vectors WHERE company_id = %s", (TEST_COMPANY_ID,))
    connection.commit()
    connection.close()


def make_category_rows() -> list[dict]:
    return [
        {
            "language": "hu",
            "narrative": "teszt narrativa",
            "embedding": FAKE_VECTOR,
            "bm25_tokens": "teszt token",
            "metadata": {"status": "OK"},
            "content_hash": "hash_hu",
        },
        {
            "language": "en",
            "narrative": "test narrative",
            "embedding": FAKE_VECTOR,
            "bm25_tokens": "test token",
            "metadata": {"status": "OK"},
            "content_hash": "hash_en",
        },
    ]


def make_company_rows() -> list[dict]:
    return [
        {
            "language": "hu",
            "chunk_index": 0,
            "content_chunk": "[CÉG:] Test Kft.\n\nteszt chunk szoveg",
            "embedding": FAKE_VECTOR,
            "bm25_tokens": "teszt chunk token",
            "metadata": {},
            "content_hash": "chunk_hash_hu",
        },
        {
            "language": "en",
            "chunk_index": 0,
            "content_chunk": "[COMPANY:] Test Kft.\n\ntest chunk text",
            "embedding": FAKE_VECTOR,
            "bm25_tokens": "test chunk token",
            "metadata": {},
            "content_hash": "chunk_hash_en",
        },
    ]


class TestUpsertCategoryVectors:
    def test_inserts_rows_with_correct_bm25_column(self, conn):
        upsert_category_vectors(conn, TEST_CATEGORY_ID, make_category_rows())

        with conn.cursor() as cur:
            cur.execute(
                "SELECT language, bm25_tokens_hu IS NOT NULL, bm25_tokens_en IS NOT NULL "
                "FROM category_vectors WHERE category_id = %s ORDER BY language",
                (TEST_CATEGORY_ID,),
            )
            rows = cur.fetchall()

        assert rows == [("en", False, True), ("hu", True, False)]

    def test_rerun_replaces_not_duplicates(self, conn):
        upsert_category_vectors(conn, TEST_CATEGORY_ID, make_category_rows())
        upsert_category_vectors(conn, TEST_CATEGORY_ID, make_category_rows())

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,))
            count = cur.fetchone()[0]

        assert count == 2

    def test_get_content_hash(self, conn):
        upsert_category_vectors(conn, TEST_CATEGORY_ID, make_category_rows())
        assert get_category_content_hash(conn, TEST_CATEGORY_ID, "hu") == "hash_hu"

    def test_get_content_hash_returns_none_when_absent(self, conn):
        assert get_category_content_hash(conn, "NONEXISTENT_ID", "hu") is None


class TestUpsertCompanyVectors:
    def test_inserts_chunk_rows(self, conn):
        upsert_company_vectors(conn, TEST_COMPANY_ID, make_company_rows())

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM company_vectors WHERE company_id = %s", (TEST_COMPANY_ID,)
            )
            count = cur.fetchone()[0]

        assert count == 2

    def test_get_content_hash(self, conn):
        upsert_company_vectors(conn, TEST_COMPANY_ID, make_company_rows())
        assert get_company_content_hash(conn, TEST_COMPANY_ID, "en") == "chunk_hash_en"


class TestAtomicSwapRollback:
    def test_failed_transaction_leaves_original_rows_intact(self, conn):
        upsert_category_vectors(conn, TEST_CATEGORY_ID, make_category_rows())

        with conn.cursor() as cur:
            cur.execute(
                "SELECT language, narrative FROM category_vectors "
                "WHERE category_id = %s ORDER BY language",
                (TEST_CATEGORY_ID,),
            )
            baseline = cur.fetchall()

        with pytest.raises(RuntimeError):
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,)
                    )
                    raise RuntimeError("simulated crash before re-insert")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT language, narrative FROM category_vectors "
                "WHERE category_id = %s ORDER BY language",
                (TEST_CATEGORY_ID,),
            )
            after_crash = cur.fetchall()

        assert after_crash == baseline
