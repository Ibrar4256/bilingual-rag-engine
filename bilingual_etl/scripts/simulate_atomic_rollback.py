"""
Atomic Swap Rollback Simulation (R11, AC-4)

Proves the atomic-swap guarantee under a simulated crash: inserts baseline
rows for a fake category, then deliberately triggers a failure partway
through a DELETE+INSERT update, and confirms the transaction rolled back
cleanly — leaving the ORIGINAL rows fully intact, not a partial mix of
old and new (or worse, zero rows).

Run:
    python -m bilingual_etl.scripts.simulate_atomic_rollback
"""

from loguru import logger
from psycopg2.extras import Json

from bilingual_etl.load.db import get_connection

TEST_CATEGORY_ID = "SIMULATION_TEST_CATEGORY_999999"

BASELINE_ROWS = [
    {"language": "hu", "narrative": "eredeti hu narrativa", "content_hash": "baseline_hash_hu"},
    {"language": "en", "narrative": "original en narrative", "content_hash": "baseline_hash_en"},
]


def _insert_baseline(conn) -> None:
    with conn:
        with conn.cursor() as cur:
            for row in BASELINE_ROWS:
                cur.execute(
                    """
                    INSERT INTO category_vectors
                        (category_id, language, narrative, embedding, metadata, content_hash)
                    VALUES (%s, %s, %s, %s::vector, %s, %s)
                    """,
                    (
                        TEST_CATEGORY_ID,
                        row["language"],
                        row["narrative"],
                        "[" + ",".join(["0.0"] * 768) + "]",
                        Json({}),
                        row["content_hash"],
                    ),
                )


def _attempt_swap_with_simulated_crash(conn) -> None:
    """Mimics upsert_category_vectors(), but deliberately raises mid-transaction
    after the DELETE and one successful INSERT — never issued a COMMIT."""
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,))
            cur.execute(
                """
                INSERT INTO category_vectors
                    (category_id, language, narrative, embedding, metadata, content_hash)
                VALUES (%s, %s, %s, %s::vector, %s, %s)
                """,
                (
                    TEST_CATEGORY_ID,
                    "hu",
                    "narrativa amely soha nem kerul commitolasra",
                    "[" + ",".join(["0.0"] * 768) + "]",
                    Json({}),
                    "hash_that_never_commits",
                ),
            )
            raise RuntimeError("Simulated crash mid-transaction (e.g. process killed, network drop)")


def _fetch_current_rows(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT language, narrative, content_hash FROM category_vectors "
            "WHERE category_id = %s ORDER BY language",
            (TEST_CATEGORY_ID,),
        )
        return cur.fetchall()


def run_simulation() -> bool:
    conn = get_connection()
    logger.info("EVIDENCE_ATOMIC_SWAP_SIMULATION_START")

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,))

        _insert_baseline(conn)
        baseline_snapshot = _fetch_current_rows(conn)
        logger.info(f"Baseline established: {len(baseline_snapshot)} row(s)")

        try:
            _attempt_swap_with_simulated_crash(conn)
        except RuntimeError as e:
            logger.info(f"EVIDENCE_ATOMIC_SWAP_SIMULATED_FAILURE_CAUGHT: {e}")

        post_crash_snapshot = _fetch_current_rows(conn)
        rollback_ok = post_crash_snapshot == baseline_snapshot

        logger.info(
            f"EVIDENCE_ATOMIC_SWAP_ROLLBACK_RESULT: rollback_ok={str(rollback_ok).lower()} "
            f"(baseline_rows={len(baseline_snapshot)}, post_crash_rows={len(post_crash_snapshot)})"
        )

        return rollback_ok
    finally:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM category_vectors WHERE category_id = %s", (TEST_CATEGORY_ID,))
        conn.close()
        logger.info("EVIDENCE_ATOMIC_SWAP_SIMULATION_DONE")


if __name__ == "__main__":
    ok = run_simulation()
    if not ok:
        raise SystemExit("Atomic swap rollback simulation FAILED — rollback_ok was false.")
