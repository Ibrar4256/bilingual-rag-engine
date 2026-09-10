---
paths: data/**, bilingual_etl/extract/**, bilingual_etl/load/**
---

# Data Handling Rules

- Never write to `data/*.json` — these are read-only source exports. All transformation output goes to Postgres, never back into `data/`.
- `data/category_company_data.json` is out of scope for ingestion (SPEC.md §3, stale/test export) — do not wire it into `bilingual_etl/extract/source.py` without flagging it first.
- Normalize inconsistent source encodings at the extraction boundary, not downstream: list fields arrive as either native JSON arrays or stringified-JSON strings for the same conceptual type — detect and coerce both to native lists in `extract/source.py` before anything downstream sees them.
- Numeric-looking fields (`nr_employees`, `year_founded`, `registered_capital`, `profit_after_tax`) arrive as strings in the source data — cast explicitly, don't rely on implicit coercion.
- `description` is null/empty for ~34% of company records — enrichment and narrative building must have a defined fallback (using `activities`/`categories`/other fields), not a skip branch.
- Every write to `category_vectors` / `company_vectors` must go through the atomic-swap path in `load/pgvector_client.py` (transactional DELETE+INSERT) — never a bare `UPDATE` or partial insert.
- Content-hash checks (R10) happen before any OpenAI call, not after — the hash gate exists to avoid the API call, not just to avoid the DB write.
