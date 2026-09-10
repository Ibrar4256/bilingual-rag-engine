# SPEC.md

Implementation spec derived from `REQUIREMENTS.md`. This is the source of truth for what gets built. If asked to build something not traceable to a requirement here, flag it before proceeding.

---

## 1. Requirement → Feature Mapping

### ETL Pipeline (`bilingual_etl/`)

| Req | Feature | Module |
|---|---|---|
| R1 | Extract categories/companies from source (currently `data/*.json`; swappable for live Postgres later) | `bilingual_etl/extract/source.py` |
| R2 | Strip HTML from descriptions (BeautifulSoup, no LLM) | `bilingual_etl/transform/html_cleaner.py` |
| R3 | HU↔EN translation for missing-language content (via R22 provider abstraction) | `bilingual_etl/enrichment/translator.py` |
| R4 | Source-language detection (langdetect) | `bilingual_etl/enrichment/language_detector.py` |
| R5 | AI enrichment: `ai_type`, `status`, SEO keywords, `recommended_headline`, `synthetic_questions`, `topic_suggestions` (via R22 provider abstraction) | `bilingual_etl/enrichment/ai_enrichment.py` |
| R6 | Narrative Template generation (prose, category list near end) | `bilingual_etl/transform/narrative_builder.py` |
| R7 | Company chunking (≤500 words) + bilingual context headers | `bilingual_etl/transform/chunker.py` |
| R8 | Protected Terms masking/unmasking (whitelist + regex) | `bilingual_etl/nlp/protected_terms.py` |
| R9 | Dual-path indexing: embeddings via R23 provider abstraction (raw narrative) + BM25 tokens (lemmatized) | `bilingual_etl/nlp/lemmatizer.py`, `bilingual_etl/load/embeddings.py` |
| R10 | Hash-based change detection (content hash gate) | `bilingual_etl/transform/hash_gate.py` |
| R11 | Atomic Swap (transactional DELETE+INSERT) | `bilingual_etl/load/pgvector_client.py` |
| R12 | Schema: `category_vectors`, `company_vectors` | `bilingual_etl/load/schema.sql` |
| — | Orchestration entrypoints (match UAT README's exact commands) | `bilingual_etl/scripts/main_etl.py`, `bilingual_etl/scripts/simulate_atomic_rollback.py` |

### Multi-Provider AI Abstraction (`bilingual_etl/providers/`)

| Req | Feature | Module |
|---|---|---|
| R22 | LLM provider abstraction (Groq, OpenRouter, Gemini) with selectable default | `bilingual_etl/providers/llm_provider.py` |
| R23 | Embedding provider abstraction (Gemini, Jina, self-hosted bge-m3) | `bilingual_etl/providers/embedding_provider.py` |
| R24 | Dynamic system prompts (DB-stored, editable via Admin UI) | `bilingual_etl/providers/prompt_store.py` |

### Admin UI (`admin-ui/`)

| Req | Feature | Module |
|---|---|---|
| R25 | React + Vite admin panel (provider dropdown, system prompt editor) | `admin-ui/src/` |
| R26 | Basic auth (username/password login, hashed credentials) | `search_api/routers/auth.py`, `admin-ui/src/auth/` |

### Search API (`search_api/`)

| Req | Feature | Module |
|---|---|---|
| R13 | Hybrid retrieval (BM25 + vector) fused via RRF (k=60) | `search_api/services/rrf.py` |
| R14 | Bilingual RRF weighting (secondary-language BM25 × 0.5) | `search_api/services/rrf.py` |
| R15 | `POST /search/category` | `search_api/routers/category.py` |
| R16 | `POST /match/companies` (JSONB pre-filters, Partner Boost ×1.15) | `search_api/routers/companies.py` |
| R17 | `POST /search/single-company` (whitelabel) | `search_api/routers/companies.py` |
| R18 | `GET /health` (DB, vector index, BM25, API connectivity) | `search_api/routers/health.py` |
| R19 | Cross-language fallback on low-relevance results | `search_api/services/language_router.py` |
| R20 | Response shape: `detected_language`, `response_time_ms`, `retrieval_mode` | `search_api/models/responses.py` |
| R21 | Independent Dockerfiles + `docker-compose.yml` | `bilingual_etl/Dockerfile`, `search_api/Dockerfile`, `admin-ui/Dockerfile`, `docker-compose.yml` |

---

## 2. Data Model

Derived from `data/*.json` (see REQUIREMENTS.md §4) and the schema described in the RFQ/Technical Spec.

```sql
-- Embedding dimension is configurable per provider (see R23):
--   Gemini gemini-embedding-001: 768 or 1536 (configurable via MRL)
--   Jina jina-embeddings-v3: 1024
--   Self-hosted bge-m3: 1024
-- Default to 768 (smallest Gemini MRL that preserves quality at this scale).
-- If the provider changes, re-run the full ETL to regenerate all embeddings.

-- category_vectors: one row per language per category
CREATE TABLE category_vectors (
    id              BIGSERIAL PRIMARY KEY,
    category_id     TEXT NOT NULL,
    language        TEXT NOT NULL CHECK (language IN ('hu', 'en')),
    narrative       TEXT NOT NULL,
    embedding       VECTOR(768),
    bm25_tokens_hu  TSVECTOR,
    bm25_tokens_en  TSVECTOR,
    metadata        JSONB NOT NULL DEFAULT '{}',
    content_hash    TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (category_id, language)
);

-- company_vectors: chunked, one row per chunk per language
CREATE TABLE company_vectors (
    id              BIGSERIAL PRIMARY KEY,
    company_id      TEXT NOT NULL,
    language        TEXT NOT NULL CHECK (language IN ('hu', 'en')),
    chunk_index     INT NOT NULL,
    content_chunk   TEXT NOT NULL,
    embedding       VECTOR(768),
    bm25_tokens_hu  TSVECTOR,
    bm25_tokens_en  TSVECTOR,
    metadata        JSONB NOT NULL DEFAULT '{}',
    is_highlighted  BOOLEAN NOT NULL DEFAULT false,
    content_hash    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, language, chunk_index)
);

-- app_config: stores active provider selection + dynamic system prompts (R22-R24)
CREATE TABLE app_config (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Seeded keys: 'llm_provider', 'embedding_provider', 'prompt_translation', 'prompt_enrichment', 'auth_users'

-- indexes: pgvector (HNSW/IVFFlat) on embedding, GIN on bm25_tokens_*, GIN on metadata, B-tree on category_id/company_id
```

**Source field mapping** (from `data/*.json` → pipeline input):
- `companies_data_for_vectors_sample_2026_03_11.json` → primary company source. Known issues to handle in `bilingual_etl/extract/source.py`: numeric fields (`nr_employees`, `year_founded`, `registered_capital`, `profit_after_tax`) arrive as strings and must be cast; list fields (`brands`, `certificates`, `services`) arrive as stringified JSON and must be `json.loads`'d, while others (`target_audience`, `logistics_capabilities`) are already native arrays — normalize both to native lists.
- `categories_export_2026_04_14T11_17_15Z.json` → canonical category taxonomy (3,000 records, use this over the smaller `category_company_data.json`).
- `category_company_data.json` → **out of scope for v1 ingestion** (see §3) — low ID overlap with the other two files indicates a stale/test export.
- Records with `description` null/empty (34% of companies) still get a narrative generated from `activities`, `categories`, and other populated fields per R6 — cannot skip enrichment just because `description` is empty.
- `address` is empty in 100% of the company sample — no per-record signal, so it's carried through as-is (empty), not treated as a data-quality failure to block on.

---

## 3. Out of Scope (v1)

- Live PostgreSQL source connection — v1 reads from `data/*.json` directly (per your decision in REQUIREMENTS.md §5a). Swapping to a live DB source is a future change isolated to `bilingual_etl/extract/source.py`.
- `category_company_data.json` — not ingested in v1; flagged as a stale/test export in REQUIREMENTS.md §4.
- Cloud/production deployment — local Docker Compose only.
- Authentication or rate-limiting on the Search API endpoints — no requirement specifies this; flagged as an open gap in REQUIREMENTS.md §3. (Note: the Admin UI *does* have basic auth per R26; search endpoints do not.)
- "Scraped web content" as a data source — contradicted requirement, not implemented.
- Dify chatbot integration itself — only the `/search/category` endpoint it would consume is in scope.

---

## 4. Acceptance Criteria

Every criterion below is written to be satisfiable directly by the evidence format in `Client_UAT_Evidence_README.md` (timestamped `EVIDENCE_*` log markers, DB query snippets, request/response payload captures) — see REQUIREMENTS.md §5.

| Feature | Acceptance Criterion | Evidence Artifact |
|---|---|---|
| Hash-based change detection (R10) | Immediate rerun with no source changes logs `EVIDENCE_AC_HASH_SKIP_CATEGORY` / `EVIDENCE_AC_HASH_SKIP_COMPANY` and `OpenAI calls = 0` | `logs/runtime.log` excerpt |
| Protected Terms (R8) | A record containing a whitelisted brand/code survives lemmatization unaltered in `bm25_tokens_hu`/`bm25_tokens_en` | DB query snippet on `category_vectors`/`company_vectors` |
| Dual-path indexing (R9) | A sample row has both `embedding` and `bm25_tokens_*` populated, tagged `EVIDENCE_AC_DUAL_PATH_CATEGORY` / `EVIDENCE_AC_DUAL_PATH_COMPANY` | DB query output (2-3 rows) |
| Atomic Swap (R11) | `simulate_atomic_rollback.py` run shows `EVIDENCE_ATOMIC_SWAP_SIMULATED_FAILURE_CAUGHT` then `EVIDENCE_ATOMIC_SWAP_ROLLBACK_RESULT` with `rollback_ok=true`, and a post-check query shows zero partial rows | `logs/runtime.log` excerpt + DB post-check query |
| Bilingual parity (R3, R6) | Same category/company has both an HU and EN row with narrative + synthetic questions | One HU + one EN sample row |
| Hybrid RRF search (R13, R14) | `/search/category`, `/match/companies`, `/search/single-company` each return `retrieval_mode: "hybrid_rrf"` with both BM25 and vector candidates present in the fusion context, tagged `EVIDENCE_API_RRF_MERGE` | 3 request/response payload pairs |
| Latency (NFR) | `/search/category` p95 < 500ms; `/match/companies` p99 < 3s (stricter target per REQUIREMENTS.md §5a); `/health` < 50ms | Timed request logs or a small load-test script output |
| Cross-language fallback (R19) | A query in one language with below-threshold results returns results from the other-language index | Request/response pair showing fallback triggered |
| Multi-provider LLM (R22) | ETL runs successfully with at least two different LLM providers (e.g. Groq then Gemini), each logging which provider served the call | `logs/runtime.log` excerpts showing provider name per call |
| Multi-provider embedding (R23) | ETL generates valid embeddings with the primary provider (Gemini) and the fallback (Jina), both producing searchable results | DB query showing embedding column populated + a search returning results |
| Dynamic prompts (R24) | Changing a system prompt via Admin UI (R25) and re-running ETL produces output reflecting the new prompt (e.g. a changed enrichment format) | Before/after enrichment output comparison |
| Admin UI (R25) | Provider dropdown changes active provider; system prompt editor saves and displays current prompt; page loads behind login wall | Browser screenshot(s) of the admin panel |
| Basic auth (R26) | Unauthenticated request to admin UI redirects to login; valid credentials grant access; invalid credentials are rejected | Request/response pair or screenshot |

---

## 5. Requirements Traceability Table

*Updated throughout the project as features are built. Empty until Phase 3 begins.*

| Req ID | Feature | Implementing File(s) | Test(s) | UAT Evidence Artifact | Status |
|---|---|---|---|---|---|
| R1 | Source extraction | `bilingual_etl/extract/source.py` | `tests/etl/test_source.py` | — | Built + tested |
| R2 | HTML cleaning | `bilingual_etl/transform/html_cleaner.py` | `tests/etl/test_html_cleaner.py` | — | Built + tested |
| R3 | Translation | `bilingual_etl/enrichment/translator.py` | `tests/etl/test_translator.py` | `uat-evidence/R3-R6-bilingual-parity/hu_en_sample_pair.txt` | Done (AC-5); live-verified against Gemini + Groq |
| R4 | Language detection | `bilingual_etl/enrichment/language_detector.py` | `tests/etl/test_language_detector.py` | — | Built + tested |
| R5 | AI enrichment | `bilingual_etl/enrichment/ai_enrichment.py` | `tests/etl/test_ai_enrichment.py` | — | Built + tested (live-verified against Gemini + Groq) |
| R6 | Narrative builder | `bilingual_etl/transform/narrative_builder.py` | `tests/etl/test_narrative_builder.py` | `uat-evidence/R3-R6-bilingual-parity/hu_en_sample_pair.txt` | Done (AC-5) |
| R7 | Company chunking | `bilingual_etl/transform/chunker.py` | `tests/etl/test_chunker.py` | `uat-evidence/R9-dual-path/company_dual_path_query.txt` (chunk headers visible) | Built + tested (verified against real 625-category record) |
| R8 | Protected terms | `bilingual_etl/nlp/protected_terms.py` | `tests/etl/test_protected_terms.py` | DB snippet (brand term intact) | Built + tested |
| R9 | Dual-path indexing | `bilingual_etl/nlp/lemmatizer.py`, `bilingual_etl/load/embeddings.py`, `bilingual_etl/scripts/main_etl.py` | `tests/etl/test_lemmatizer.py`, `tests/etl/test_embeddings.py`, `tests/etl/test_integration.py` | `uat-evidence/R9-dual-path/{category,company}_dual_path_query.txt`, `force_run_dual_path.log` | Done (AC-3) |
| R10 | Hash gate | `bilingual_etl/transform/hash_gate.py`, `bilingual_etl/scripts/main_etl.py` | `tests/etl/test_hash_gate.py`, `tests/etl/test_integration.py` | `uat-evidence/R10-hash-gate/nonforce_rerun.log` (0 LLM calls, all 6 records skipped) | Done (AC-1) |
| R11 | Atomic swap | `bilingual_etl/load/pgvector_client.py`, `bilingual_etl/scripts/simulate_atomic_rollback.py` | `tests/etl/test_atomic_swap.py` | `uat-evidence/R11-atomic-swap/rollback_simulation.log` (all 4 markers present, `rollback_ok=true`) | Done (AC-4) |
| R12 | Schema | `bilingual_etl/load/schema.sql` | `tests/etl/test_schema.py` | — | Not started |
| R13/R14 | RRF fusion | `search_api/services/rrf.py` | `tests/search_api/test_rrf.py` | API payload w/ `hybrid_rrf` | Done — wired into all 3 live endpoints, `EVIDENCE_API_RRF_MERGE` logged per request |
| R15 | `/search/category` | `search_api/routers/category.py` | `tests/search_api/test_category.py` | Request/response pair | Done — live-verified with HU query against real data + Gemini embeddings |
| R16 | `/match/companies` | `search_api/routers/companies.py` | `tests/search_api/test_companies.py` | Request/response pair | Done — live-verified; JSONB pre-filters + Partner Boost ×1.15 implemented |
| R17 | `/search/single-company` | `search_api/routers/companies.py` | `tests/search_api/test_companies.py` | Request/response pair | Done — live-verified; scoped WHERE before vector search |
| R18 | `/health` | `search_api/routers/health.py` | `tests/search_api/test_health.py` | — | Done — live-verified against real Postgres |
| R19 | Cross-language fallback | `search_api/services/language_router.py` | `tests/search_api/test_fallback.py` | Fallback-triggered payload | Done — threshold-based fallback triggers when primary BM25 < 3 results |
| R20 | Response shape | `search_api/models/responses.py` | `tests/search_api/test_category.py`, `tests/search_api/test_companies.py` | — | Done — all endpoints return `detected_language`, `response_time_ms`, `retrieval_mode: "hybrid_rrf"` |
| R21 | Docker/Compose | `docker-compose.yml`, `bilingual_etl/Dockerfile`, `search_api/Dockerfile`, `admin-ui/Dockerfile`, `admin-ui/nginx.conf` | manual: `docker compose up --build` | All 3 containers running, health ok, admin login verified | Done — postgres + search-api + admin-ui (nginx) all containerized, verified end-to-end |
| R22 | LLM provider abstraction | `bilingual_etl/providers/llm_provider.py` | `tests/etl/test_llm_provider.py` | `uat-evidence/R22-multi-provider/gemini_then_groq.log` | Done — live-verified with two providers (Gemini, then Groq after a real free-tier 429 forced a live provider switch) |
| R23 | Embedding provider abstraction | `bilingual_etl/providers/embedding_provider.py` | `tests/etl/test_embedding_provider.py` | DB query + search result | Built + tested (live-verified: Gemini) |
| R24 | Dynamic system prompts | `bilingual_etl/providers/prompt_store.py`, `search_api/routers/admin_config.py` | `tests/etl/test_prompt_store.py`, `tests/search_api/test_admin_config.py` | Before/after comparison | Done — editable via Admin UI (`/admin/config/*`), live-verified in browser |
| R25 | Admin UI | `admin-ui/src/` | — (browser-tested) | Browser screenshot | Done — React+Vite SPA with login, provider dropdowns, prompt editor, health status; live-verified |
| R26 | Basic auth | `search_api/routers/auth.py` | `tests/search_api/test_auth.py` | Auth request/response pair | Done — bcrypt + JWT, login/reject verified in browser + tests |
