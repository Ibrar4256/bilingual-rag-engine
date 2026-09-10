---
paths: search_api/**
---

# Search API Conventions

- Every search response includes `detected_language`, `response_time_ms`, and `retrieval_mode` (R20) — no endpoint returns a bare result list.
- Fusion is always RRF (`1/(k+rank)`, k=60 default) — never a weighted average of vector and BM25 scores. This is an explicit client constraint, not a style choice.
- BM25 lookups route to the language-specific column (`bm25_tokens_hu` vs `bm25_tokens_en`) based on detected/requested language — never query both columns as a fallback without going through the explicit cross-language fallback path in `services/language_router.py`.
- `/search/single-company` must filter `WHERE company_id = X` before running vector search, not after — it's a scoping constraint, not a post-filter.
- Partner Boost (×1.15 for `is_highlighted=true`) applies only in `/match/companies`, not in `/search/category` or `/search/single-company`.
- No endpoint requires authentication in v1 (SPEC.md §3, explicit client gap) — don't add auth middleware without flagging it as a scope addition first.
