"""
Hash Gate (R10)

Computes a deterministic MD5 content hash for a category/company record so
the ETL can skip re-translation, re-enrichment, and re-embedding for records
that haven't changed since the last run — the source data changes rarely,
but translation + enrichment + embedding are the slowest and most
rate-limit-sensitive stages, so skipping them on unchanged input is the
single biggest cost/time saver in the whole pipeline.

This module is a pure, reusable utility — it doesn't know or care whether
it's checking a category or a company, and doesn't decide what "skipping"
means for either (that's the orchestrator's job, in bilingual_etl/scripts/
main_etl.py, which has the category/company-specific context needed to log
the AC-1 evidence markers EVIDENCE_AC_HASH_SKIP_CATEGORY/COMPANY).

Usage:
    new_hash = compute_content_hash(record)
    if not has_changed(new_hash, previous_hash):
        skip re-processing this record
"""

import hashlib
import json


def compute_content_hash(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()


def has_changed(new_hash: str, previous_hash: str | None) -> bool:
    if previous_hash is None:
        return True
    return new_hash != previous_hash
