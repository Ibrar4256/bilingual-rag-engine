"""
Integration tests for the ETL orchestrator (Phase J).

LLM/embedding calls are mocked (consistent with every other phase's tests —
fast, deterministic, free), but everything else runs for real against the
local dev Postgres: hash-gate decisions, narrative building, chunking,
lemmatization, and the atomic-swap DB writes. This tests the ORCHESTRATION
wiring — does process_categories/process_companies make the right
skip/process decisions and produce correctly-shaped rows — not the
individual stage logic, which each has its own dedicated test file.

Requires the local dev Postgres container running. Skips gracefully if
unreachable, rather than failing the whole suite.
"""

from unittest.mock import patch

import psycopg2
import pytest

from bilingual_etl.load.db import get_connection
from bilingual_etl.scripts.main_etl import (
    build_category_names_lookup,
    process_categories,
    process_companies,
)
from bilingual_etl.nlp.protected_terms import ProtectedTermsMasker

TEST_CATEGORY_ID = "TEST_INTEGRATION_CATEGORY"
TEST_COMPANY_ID = "TEST_INTEGRATION_COMPANY"

FAKE_CATEGORY = {
    "category_id": TEST_CATEGORY_ID,
    "category_name": "Teszt kategória",
    "hierarchy": ["Teszt"],
    "short_description": "Rövid leírás.",
    "description": "Hosszabb leírás a teszt kategóriáról.",
    "synonyms": "",
    "supplements": [],
}

FAKE_COMPANY = {
    "company_id": TEST_COMPANY_ID,
    "company_name": "Teszt Kft.",
    "year_founded": 2000,
    "nr_employees": 10,
    "legal_form": "Korlátolt felelősségű társaság",
    "company_status": "Működő",
    "description": "A Teszt Kft. ipari alkatrészeket gyárt.",
    "activities": ["gyártás"],
    "services": ["manufacturing"],
    "certificates": ["ISO 9001"],
    "brands": ["TestBrand"],
    "counties": ["Pest megye"],
    "categories": {TEST_CATEGORY_ID: {"category_id": TEST_CATEGORY_ID, "category_name": "Teszt kategória"}},
}


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


@pytest.fixture
def masker():
    return ProtectedTermsMasker()


FAKE_ENRICHMENT = {
    "ai_type": "GÉP_ÉS_BERENDEZÉS",
    "status": "OK",
    "add_words": ["test"],
    "recommended_headline": "Test headline",
    "synthetic_questions": ["Test question?"],
    "topic_suggestions": [],
}


def _patched():
    return (
        patch("bilingual_etl.scripts.main_etl.translate", side_effect=lambda text, *a, **k: f"[EN] {text}"),
        patch("bilingual_etl.scripts.main_etl.enrich", return_value=dict(FAKE_ENRICHMENT)),
        patch("bilingual_etl.scripts.main_etl.embed_texts", side_effect=lambda texts: [[0.0] * 768 for _ in texts]),
    )


class TestProcessCategories:
    def test_first_run_processes_and_writes_dual_path_rows(self, conn, masker):
        p1, p2, p3 = _patched()
        with p1, p2, p3:
            processed, skipped, failed = process_categories(conn, [FAKE_CATEGORY], masker)

        assert (processed, skipped, failed) == (1, 0, 0)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT language, bm25_tokens_hu IS NOT NULL, bm25_tokens_en IS NOT NULL, "
                "array_length(embedding::real[], 1) FROM category_vectors "
                "WHERE category_id = %s ORDER BY language",
                (TEST_CATEGORY_ID,),
            )
            rows = cur.fetchall()

        assert rows == [("en", False, True, 768), ("hu", True, False, 768)]

    def test_second_run_skips_unchanged(self, conn, masker):
        p1, p2, p3 = _patched()
        with p1, p2, p3:
            process_categories(conn, [FAKE_CATEGORY], masker)
            processed, skipped, failed = process_categories(conn, [FAKE_CATEGORY], masker)

        assert (processed, skipped, failed) == (0, 1, 0)

    def test_force_flag_reprocesses_unchanged(self, conn, masker):
        p1, p2, p3 = _patched()
        with p1, p2, p3:
            process_categories(conn, [FAKE_CATEGORY], masker)
            processed, skipped, failed = process_categories(conn, [FAKE_CATEGORY], masker, force=True)

        assert (processed, skipped, failed) == (1, 0, 0)

    def test_failure_in_one_record_does_not_abort_batch(self, conn, masker):
        broken_category = {
            **FAKE_CATEGORY,
            "category_id": "TEST_INTEGRATION_CATEGORY_BROKEN",
            "category_name": "Törött kategória",
        }

        def flaky_translate(text, *a, **k):
            if text == "Törött kategória":
                raise RuntimeError("simulated LLM failure")
            return f"[EN] {text}"

        p2, p3 = _patched()[1], _patched()[2]
        with p2, p3, patch("bilingual_etl.scripts.main_etl.translate", side_effect=flaky_translate):
            processed, skipped, failed = process_categories(conn, [FAKE_CATEGORY, broken_category], masker)

        assert (processed, skipped, failed) == (1, 0, 1)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM category_vectors WHERE category_id = %s",
                ("TEST_INTEGRATION_CATEGORY_BROKEN",),
            )
            assert cur.fetchone()[0] == 0
            cur.execute(
                "SELECT COUNT(*) FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,)
            )
            assert cur.fetchone()[0] == 2

        with conn.cursor() as cur:
            cur.execute("DELETE FROM category_vectors WHERE category_id = %s", ("TEST_INTEGRATION_CATEGORY_BROKEN",))
        conn.commit()


class TestBuildCategoryNamesLookup:
    def test_lookup_reflects_stored_metadata(self, conn, masker):
        p1, p2, p3 = _patched()
        with p1, p2, p3:
            process_categories(conn, [FAKE_CATEGORY], masker)

        lookup = build_category_names_lookup(conn)

        assert lookup[TEST_CATEGORY_ID]["hu"] == "Teszt kategória"
        assert lookup[TEST_CATEGORY_ID]["en"] == "[EN] Teszt kategória"


class TestProcessCompanies:
    def test_first_run_processes_and_writes_chunk_rows(self, conn, masker):
        p1, p2, p3 = _patched()
        with p1, p2, p3:
            process_categories(conn, [FAKE_CATEGORY], masker)
            lookup = build_category_names_lookup(conn)
            processed, skipped, failed = process_companies(conn, [FAKE_COMPANY], masker, lookup)

        assert (processed, skipped, failed) == (1, 0, 0)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT language, bm25_tokens_hu IS NOT NULL, bm25_tokens_en IS NOT NULL "
                "FROM company_vectors WHERE company_id = %s ORDER BY language",
                (TEST_COMPANY_ID,),
            )
            rows = cur.fetchall()

        assert rows == [("en", False, True), ("hu", True, False)]

    def test_chunk_contains_category_name_and_header(self, conn, masker):
        p1, p2, p3 = _patched()
        with p1, p2, p3:
            process_categories(conn, [FAKE_CATEGORY], masker)
            lookup = build_category_names_lookup(conn)
            process_companies(conn, [FAKE_COMPANY], masker, lookup)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT content_chunk FROM company_vectors WHERE company_id = %s AND language = 'hu'",
                (TEST_COMPANY_ID,),
            )
            chunk = cur.fetchone()[0]

        assert "[CÉG:] Teszt Kft." in chunk
        assert "Teszt kategória" in chunk

    def test_second_run_skips_unchanged(self, conn, masker):
        p1, p2, p3 = _patched()
        with p1, p2, p3:
            process_categories(conn, [FAKE_CATEGORY], masker)
            lookup = build_category_names_lookup(conn)
            process_companies(conn, [FAKE_COMPANY], masker, lookup)
            processed, skipped, failed = process_companies(conn, [FAKE_COMPANY], masker, lookup)

        assert (processed, skipped, failed) == (0, 1, 0)
