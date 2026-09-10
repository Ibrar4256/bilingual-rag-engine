# CLAUDE.md

## Tech Stack (and why)

- **Python 3.10+** — mandated by client spec; matches huspacy/spaCy model compatibility.
- **PostgreSQL 15+ with pgvector** — single store for vector embeddings, BM25 `tsvector` columns, and app config (dual-path indexing + dynamic config requirements).
- **FastAPI** — client-preferred; async, OpenAPI docs generation satisfies the Swagger deliverable. Also serves the Admin UI's backend API (auth, config CRUD).
- **React + Vite** — admin panel frontend (R25). Lightweight, fast dev server, built as static assets served by its own container or the FastAPI backend.
- **LLM providers (multi-provider, R22)**: Groq, OpenRouter, Google Gemini — selectable at runtime via Admin UI. Code never calls a provider directly; all text-generation goes through `bilingual_etl/providers/llm_provider.py`.
- **Embedding providers (multi-provider, R23)**: Google Gemini `gemini-embedding-001` (primary, free, configurable dims), Jina AI `jina-embeddings-v3` (fallback, 10M free tokens), self-hosted BAAI/bge-m3 via `sentence-transformers` (offline fallback). Selectable via Admin UI.
- **huspacy `hu_core_news_lg`** — Hungarian lemmatization for BM25 path.
- **spaCy `en_core_web_lg`** — English lemmatization for BM25 path.
- **Docker Compose** — local-only deployment target (no cloud target specified — see REQUIREMENTS.md §5a).

## Build / Test / Run

```bash
docker compose up -d postgres                      # start Postgres+pgvector only
python -m bilingual_etl.scripts.main_etl            # run full ETL (matches UAT evidence commands)
python -m bilingual_etl.scripts.main_etl --force-enrichment   # force reprocess
python -m bilingual_etl.scripts.simulate_atomic_rollback      # atomic-swap rollback proof
uvicorn search_api.main:app --reload --port 8000    # run Search API locally
cd admin-ui && npm run dev                          # run Admin UI dev server
pytest tests/                                       # run all tests
docker compose up --build                           # full stack (postgres + etl + api + admin-ui)
```

## Code Style (deviations from language defaults)

- Every ETL stage that mutates DB state or skips work must log via `loguru` with an `EVIDENCE_*` marker matching the names in `Client_UAT_Evidence_README.md` — these markers are the UAT proof mechanism, not optional logging.
- Never lemmatize before the Protected Terms mask/unmask pass (R8) — masking order is a correctness requirement, not a style preference.
- RRF fusion (never a weighted average of scores) — the Technical Spec explicitly forbids `0.7*vector + 0.3*bm25`-style blending.
- Language-specific data (HU/EN) is always a parallel pair of rows, never a single row with two language columns — matches the `category_vectors`/`company_vectors` schema in SPEC.md.
- Never call an LLM or embedding API directly — always go through `bilingual_etl/providers/llm_provider.py` or `embedding_provider.py`. Every call must log the provider name used, so UAT evidence shows which provider served each operation.
- System prompts for translation and enrichment are read from the `app_config` DB table at the start of each ETL run, not from hardcoded strings — R24 requires them to be editable via the Admin UI without redeployment.

## Project Structure

```
bilingual_etl/       # ETL pipeline (independent Docker service)
  extract/           # source ingestion (data/*.json today, swappable for live DB)
  transform/         # HTML cleaning, narrative building, chunking, hash gate
  enrichment/         # translation, language detection, AI enrichment
  nlp/                # protected terms, lemmatization
  load/               # pgvector client, atomic swap, schema
  providers/          # multi-provider abstraction: llm_provider, embedding_provider, prompt_store
  scripts/            # main_etl.py, simulate_atomic_rollback.py (entrypoints)
search_api/           # Search microservice + Admin API backend (independent Docker service)
  routers/            # /search/category, /match/companies, /search/single-company, /health, /auth, /admin/config
  services/           # RRF fusion, cross-language fallback
  models/             # request/response schemas
admin-ui/             # React + Vite admin panel (independent Docker service)
  src/                # components, pages, auth
tests/                # mirrors bilingual_etl/ and search_api/
data/                 # source JSON exports (see REQUIREMENTS.md §4)
docs/
  requirements/       # original client PDFs
  learning/           # learning trail (Phase 5) — one .md + .pdf per concept, INDEX.md
uat-evidence/         # captured evidence artifacts, per Client_UAT_Evidence_README.md format
.claude/
  rules/              # path-scoped rules (data-handling, api-conventions, bilingual-nlp, admin-ui)
  agents/             # reviewer, researcher, data-validator
  skills/             # learning-doc-generator, uat-evidence-pack
```

## Source of Truth

Full requirements traceability lives in `REQUIREMENTS.md` and `SPEC.md` — treat these as authoritative. If asked to build something not traceable to a requirement in `SPEC.md`, flag it before proceeding.

`SPEC.md` §5 has a live traceability table (requirement → file → test → UAT evidence) — update it whenever a feature lands.
