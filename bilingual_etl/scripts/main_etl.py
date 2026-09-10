"""
Main ETL Orchestrator (Phase J)

Wires together every stage built in Phases B through I into one pipeline:

    extract -> clean HTML -> hash-gate -> translate -> AI-enrich ->
    build narrative -> (companies only: append questions + chunk) ->
    mask/lemmatize for BM25 -> embed -> atomic-swap upsert

Categories are processed before companies so that each category's
(possibly freshly-translated) name is already in the database by the time
company narratives need to render their category lists — company narratives
look up category names from category_vectors.metadata rather than
re-translating the same category name once per company that references it.

A failure on one record (e.g. an LLM call exhausting its retries under a
rate limit) is logged as an error and that record is skipped — it must
never produce a partial write (per bilingual-nlp.md: a translation failure
is a pipeline error to surface, not a reason to write a single-language
row), but it also must not abort a multi-hour batch run over one bad record.

Usage:
    python -m bilingual_etl.scripts.main_etl
    python -m bilingual_etl.scripts.main_etl --force-enrichment
    python -m bilingual_etl.scripts.main_etl --limit 5
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests as http_requests
from loguru import logger

from bilingual_etl.enrichment.ai_enrichment import enrich
from bilingual_etl.enrichment.translator import translate
from bilingual_etl.extract.source import extract_categories, extract_companies
from bilingual_etl.load.db import get_connection
from bilingual_etl.load.embeddings import embed_texts
from bilingual_etl.load.pgvector_client import (
    get_category_content_hash,
    get_company_content_hash,
    upsert_category_vectors,
    upsert_company_vectors,
)
from bilingual_etl.nlp.lemmatizer import lemmatize_for_bm25
from bilingual_etl.nlp.protected_terms import ProtectedTermsMasker
from bilingual_etl.transform.chunker import append_synthetic_questions, chunk_company_narrative
from bilingual_etl.transform.hash_gate import compute_content_hash, has_changed
from bilingual_etl.transform.html_cleaner import strip_html
from bilingual_etl.transform.narrative_builder import build_category_narrative, build_company_narrative, join_natural

# See REQUIREMENTS.md §5a: no source field is documented as driving Premium
# Partner status. `signal_lamp` looks tempting but most plausibly represents
# a business/credit-health rating, not a subscription tier — defaulting to
# false rather than guessing.
DEFAULT_IS_HIGHLIGHTED = False

LOG_DIR = Path(__file__).parent.parent.parent / "logs"


def _update_etl_progress(conn, data: dict) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_config (key, value) VALUES ('etl_progress', %s::jsonb) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (json.dumps(data),),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to update ETL progress: {e}")


def _send_etl_webhook(conn, summary: dict) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value->>'url' FROM app_config WHERE key = 'etl_webhook'")
            row = cur.fetchone()
        if not row or not row[0]:
            return
        url = row[0]
        http_requests.post(url, json=summary, timeout=10)
        logger.info(f"ETL webhook sent to {url}")
    except Exception as e:
        logger.warning(f"ETL webhook failed: {e}")


def configure_logging() -> None:
    """Adds a persistent file sink alongside loguru's default stderr sink, so
    every run leaves a timestamped record on disk — the UAT evidence pack
    (docs/Client_UAT_Evidence_README.md) is built entirely from log excerpts,
    and capturing those shouldn't depend on remembering to redirect stdout."""
    LOG_DIR.mkdir(exist_ok=True)
    logger.add(
        LOG_DIR / "runtime.log",
        rotation="10 MB",
        retention=5,
        level="INFO",
    )


def _profile_line(company: dict, language: str) -> str:
    activities = company.get("activities") or []
    if not activities:
        return company.get("company_name", "")
    return join_natural(activities[:3], language)


def _process_one_category(conn, category: dict, masker: ProtectedTermsMasker, force: bool) -> bool:
    """Returns True if the category was processed, False if skipped (hash unchanged)."""
    category = dict(category)
    category["description"] = strip_html(category.get("description", ""))
    category["short_description"] = strip_html(category.get("short_description", ""))
    category_id = category["category_id"]

    content_hash = compute_content_hash(category)
    existing_hash = get_category_content_hash(conn, category_id, "hu")

    if not force and not has_changed(content_hash, existing_hash):
        logger.info(
            f"EVIDENCE_AC_HASH_SKIP_CATEGORY: category_id={category_id} "
            f"content hash unchanged; skipping translation/enrichment/embedding"
        )
        return False

    narrative_hu = build_category_narrative(category, "hu")

    category_en = dict(category)
    category_en["category_name"] = translate(category["category_name"], "hu", "en")
    if category["description"]:
        category_en["description"] = translate(category["description"], "hu", "en")
    if category.get("hierarchy"):
        category_en["hierarchy"] = [translate(h, "hu", "en") for h in category["hierarchy"]]
    narrative_en = build_category_narrative(category_en, "en")

    enrichment_hu = enrich(narrative_hu)
    enrichment_en = enrich(narrative_en)

    bm25_hu = lemmatize_for_bm25(narrative_hu, "hu", masker)
    bm25_en = lemmatize_for_bm25(narrative_en, "en", masker)

    vectors = embed_texts([narrative_hu, narrative_en], cache_conn=conn)

    rows = [
        {
            "language": "hu",
            "narrative": narrative_hu,
            "embedding": vectors[0],
            "bm25_tokens": bm25_hu,
            "metadata": {**enrichment_hu, "category_name": category["category_name"]},
            "content_hash": content_hash,
        },
        {
            "language": "en",
            "narrative": narrative_en,
            "embedding": vectors[1],
            "bm25_tokens": bm25_en,
            "metadata": {**enrichment_en, "category_name": category_en["category_name"]},
            "content_hash": content_hash,
        },
    ]
    upsert_category_vectors(conn, category_id, rows)
    logger.info(
        f"EVIDENCE_AC_DUAL_PATH_CATEGORY: category_id={category_id} "
        f"wrote embedding+bm25 tokens for both hu and en rows"
    )
    return True


def process_categories(
    conn,
    categories: list[dict],
    masker: ProtectedTermsMasker,
    force: bool = False,
    limit: int | None = None,
    workers: int = 1,
) -> tuple[int, int, int]:
    if limit:
        categories = categories[:limit]

    total = len(categories)
    processed = skipped = failed = 0

    def _report():
        _update_etl_progress(conn, {
            "phase": "categories",
            "total": total,
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "status": "running",
            "started_at": int(time.time()),
        })

    _report()

    if workers <= 1:
        for category in categories:
            try:
                if _process_one_category(conn, category, masker, force):
                    processed += 1
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to process category_id={category.get('category_id')}: {e}")
            if (processed + skipped + failed) % 5 == 0:
                _report()
    else:
        def _worker(cat):
            worker_conn = get_connection()
            try:
                return _process_one_category(worker_conn, cat, masker, force)
            finally:
                worker_conn.close()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_worker, cat): cat for cat in categories}
            for future in as_completed(futures):
                cat = futures[future]
                try:
                    if future.result():
                        processed += 1
                    else:
                        skipped += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to process category_id={cat.get('category_id')}: {e}")
                if (processed + skipped + failed) % 5 == 0:
                    _report()

    _report()
    logger.info(f"Categories: {processed} processed, {skipped} skipped, {failed} failed (workers={workers})")
    return processed, skipped, failed


def build_category_names_lookup(conn) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT category_id, language, metadata->>'category_name' FROM category_vectors")
        for category_id, language, name in cur.fetchall():
            if name:
                lookup.setdefault(category_id, {})[language] = name
    return lookup


def _process_one_company(
    conn,
    company: dict,
    masker: ProtectedTermsMasker,
    category_names_lookup: dict[str, dict[str, str]],
    force: bool,
) -> bool:
    """Returns True if the company was processed, False if skipped (hash unchanged)."""
    company = dict(company)
    company["description"] = strip_html(company.get("description", ""))
    company_id = company["company_id"]

    content_hash = compute_content_hash(company)
    existing_hash = get_company_content_hash(conn, company_id, "hu")

    if not force and not has_changed(content_hash, existing_hash):
        logger.info(
            f"EVIDENCE_AC_HASH_SKIP_COMPANY: company_id={company_id} "
            f"content hash unchanged; skipping translation/enrichment/embedding"
        )
        return False

    category_ids = list(company.get("categories", {}).keys())
    category_names_hu = [category_names_lookup.get(cid, {}).get("hu") for cid in category_ids]
    category_names_hu = [n for n in category_names_hu if n]
    category_names_en = [category_names_lookup.get(cid, {}).get("en") for cid in category_ids]
    category_names_en = [n for n in category_names_en if n]

    # HU
    narrative_hu = build_company_narrative(company, "hu", category_names=category_names_hu)
    enrichment_hu = enrich(narrative_hu)
    narrative_hu_full = append_synthetic_questions(
        narrative_hu, enrichment_hu.get("synthetic_questions") or [], "hu"
    )
    logger.info(f"EVIDENCE_COMPANY_SYNTHETIC_QUESTIONS_APPEND: company_id={company_id} language=hu")
    chunks_hu = chunk_company_narrative(
        narrative_hu_full, company["company_name"], _profile_line(company, "hu"), "hu"
    )
    logger.info(f"EVIDENCE_COMPANY_CHUNK_HEADER: company_id={company_id} language=hu chunks={len(chunks_hu)}")

    # EN
    company_en = dict(company)
    if company["description"]:
        company_en["description"] = translate(company["description"], "hu", "en")
    company_en["activities"] = [translate(a, "hu", "en") for a in company.get("activities", [])]
    narrative_en = build_company_narrative(company_en, "en", category_names=category_names_en)
    enrichment_en = enrich(narrative_en)
    narrative_en_full = append_synthetic_questions(
        narrative_en, enrichment_en.get("synthetic_questions") or [], "en"
    )
    logger.info(f"EVIDENCE_COMPANY_SYNTHETIC_QUESTIONS_APPEND: company_id={company_id} language=en")
    chunks_en = chunk_company_narrative(
        narrative_en_full, company["company_name"], _profile_line(company_en, "en"), "en"
    )
    logger.info(f"EVIDENCE_COMPANY_CHUNK_HEADER: company_id={company_id} language=en chunks={len(chunks_en)}")

    all_chunk_texts = chunks_hu + chunks_en
    vectors = embed_texts(all_chunk_texts, cache_conn=conn)
    vectors_hu = vectors[: len(chunks_hu)]
    vectors_en = vectors[len(chunks_hu) :]

    rows = []
    for i, (chunk_text, vector) in enumerate(zip(chunks_hu, vectors_hu)):
        rows.append(
            {
                "language": "hu",
                "chunk_index": i,
                "content_chunk": chunk_text,
                "embedding": vector,
                "bm25_tokens": lemmatize_for_bm25(chunk_text, "hu", masker),
                "metadata": {k: v for k, v in enrichment_hu.items() if k != "synthetic_questions"},
                "is_highlighted": DEFAULT_IS_HIGHLIGHTED,
                "content_hash": content_hash,
            }
        )
    for i, (chunk_text, vector) in enumerate(zip(chunks_en, vectors_en)):
        rows.append(
            {
                "language": "en",
                "chunk_index": i,
                "content_chunk": chunk_text,
                "embedding": vector,
                "bm25_tokens": lemmatize_for_bm25(chunk_text, "en", masker),
                "metadata": {k: v for k, v in enrichment_en.items() if k != "synthetic_questions"},
                "is_highlighted": DEFAULT_IS_HIGHLIGHTED,
                "content_hash": content_hash,
            }
        )

    upsert_company_vectors(conn, company_id, rows)
    logger.info(
        f"EVIDENCE_AC_DUAL_PATH_COMPANY: company_id={company_id} "
        f"wrote embedding+bm25 tokens for {len(rows)} chunk row(s)"
    )
    return True


def process_companies(
    conn,
    companies: list[dict],
    masker: ProtectedTermsMasker,
    category_names_lookup: dict[str, dict[str, str]],
    force: bool = False,
    limit: int | None = None,
    workers: int = 1,
) -> tuple[int, int, int]:
    if limit:
        companies = companies[:limit]

    total = len(companies)
    processed = skipped = failed = 0

    def _report():
        _update_etl_progress(conn, {
            "phase": "companies",
            "total": total,
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "status": "running",
            "started_at": int(time.time()),
        })

    _report()

    if workers <= 1:
        for company in companies:
            try:
                if _process_one_company(conn, company, masker, category_names_lookup, force):
                    processed += 1
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to process company_id={company.get('company_id')}: {e}")
            if (processed + skipped + failed) % 5 == 0:
                _report()
    else:
        def _worker(comp):
            worker_conn = get_connection()
            try:
                return _process_one_company(worker_conn, comp, masker, category_names_lookup, force)
            finally:
                worker_conn.close()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_worker, comp): comp for comp in companies}
            for future in as_completed(futures):
                comp = futures[future]
                try:
                    if future.result():
                        processed += 1
                    else:
                        skipped += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to process company_id={comp.get('company_id')}: {e}")
                if (processed + skipped + failed) % 5 == 0:
                    _report()

    _report()
    logger.info(f"Companies: {processed} processed, {skipped} skipped, {failed} failed (workers={workers})")
    return processed, skipped, failed


def run(force: bool = False, limit: int | None = None, workers: int = 1) -> None:
    configure_logging()
    conn = get_connection()
    masker = ProtectedTermsMasker()

    logger.info(f"ETL starting with workers={workers}, force={force}, limit={limit}")

    try:
        categories = extract_categories()
        companies = extract_companies()

        cat_processed, cat_skipped, cat_failed = process_categories(
            conn, categories, masker, force=force, limit=limit, workers=workers,
        )

        category_names_lookup = build_category_names_lookup(conn)

        comp_processed, comp_skipped, comp_failed = process_companies(
            conn, companies, masker, category_names_lookup, force=force, limit=limit, workers=workers,
        )

        completion_summary = {
            "phase": "complete",
            "status": "complete",
            "categories": {"processed": cat_processed, "skipped": cat_skipped, "failed": cat_failed},
            "companies": {"processed": comp_processed, "skipped": comp_skipped, "failed": comp_failed},
            "finished_at": int(time.time()),
        }
        _update_etl_progress(conn, completion_summary)
        _send_etl_webhook(conn, completion_summary)

        logger.info(
            f"Full ETL finished — categories: {cat_processed} processed / {cat_skipped} skipped / "
            f"{cat_failed} failed, companies: {comp_processed} processed / {comp_skipped} skipped / "
            f"{comp_failed} failed"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bilingual ETL pipeline")
    parser.add_argument(
        "--force-enrichment",
        action="store_true",
        help="Reprocess every record regardless of content hash (translation/enrichment/embedding).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N categories and N companies (for controlled testing).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers for processing (default: 1, sequential).",
    )
    args = parser.parse_args()

    run(force=args.force_enrichment, limit=args.limit, workers=args.workers)
