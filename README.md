# Bilingual Search Infrastructure

**Production-grade bilingual (Hungarian/English) search engine** with AI-powered enrichment, built for a Hungarian B2B supplier directory.

Combines **vector semantic search** with **BM25 keyword search** using **Reciprocal Rank Fusion (RRF)**, supporting both Hungarian and English queries with automatic cross-language fallback.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Hybrid Search (RRF)** | Vector + BM25 fusion using Reciprocal Rank Fusion — not weighted averages |
| **Bilingual NLP** | Hungarian (huspacy) + English (spaCy) lemmatization with protected-terms masking |
| **RAG Answering** | `/ask` endpoint retrieves docs and generates answers with citations via SSE streaming |
| **Multi-Provider LLM** | 7 providers: Groq, OpenRouter, Gemini, 9Router, Cerebras, SambaNova, Generic OpenAI-compatible |
| **Multi-Provider Embeddings** | Gemini, Jina AI, self-hosted BGE-M3 |
| **Admin Dashboard** | React SPA — provider config, system prompts, ETL controls, analytics, user management |
| **Conversation History** | Chat sessions auto-saved to DB, resumable from sidebar |
| **Search Agent** | Tool-use pattern: LLM plans which search tools to call, then synthesizes results |
| **ETL Pipeline** | Extract, clean, translate, enrich, embed, and index — with hash-based change detection |
| **Atomic Rollback** | Schema swap pattern for zero-downtime re-indexing |
| **Semantic Re-ranking** | Cross-encoder re-ranking for improved result relevance |
| **Search Analytics** | Query tracking, zero-result analysis, response time monitoring |
| **LLM Observability** | Trace every LLM/embedding call — latency, tokens, provider, cost |
| **Guardrails** | Output validation on RAG answers (citation verification, hallucination check) |
| **Evaluation Pipeline** | MRR, NDCG, Recall metrics on golden test queries |
| **Rate Limiting** | Per-IP sliding window (configurable RPM), request ID tracking |
| **Security Hardening** | JWT auth, brute-force protection, SQL injection prevention, security headers, non-root Docker |
| **Connection Pooling** | ThreadedConnectionPool with configurable max connections |
| **CI/CD** | GitHub Actions: lint, type-check, test on every push |

---

## Architecture

```
                    +------------------+
                    |   Admin UI       |
                    |   React + Vite   |
                    |   Port 3000/5173 |
                    +--------+---------+
                             |
                    +--------v---------+        +-----------------+
                    |   Search API     |        |   ETL Pipeline  |
                    |   FastAPI        +------->+   Python        |
                    |   Port 8000      |        |   (subprocess)  |
                    +--------+---------+        +--------+--------+
                             |                           |
                    +--------v---------------------------v--------+
                    |           PostgreSQL + pgvector              |
                    |   category_vectors | company_vectors         |
                    |   tsvector (BM25)  | vector (768d)           |
                    |   app_config       | conversations           |
                    |   search_analytics | llm_traces              |
                    +--------------------------------------------+
```

**Search Flow:**
1. Query arrives at `/search/category` or `/match/companies`
2. Language detected (Hungarian/English)
3. **Vector path**: embed query via active provider, cosine similarity search
4. **BM25 path**: lemmatize query (huspacy/spaCy), search language-specific `tsvector` column
5. **RRF fusion**: `1/(k + rank)` merge, k=60
6. Optional cross-language fallback if primary results are sparse
7. Optional semantic re-ranking

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **API** | FastAPI (Python 3.10+) | Async, auto-generated OpenAPI docs |
| **Frontend** | React + Vite | Lightweight SPA for admin panel |
| **Database** | PostgreSQL 16 + pgvector | Single store for vectors, BM25, config |
| **Hungarian NLP** | huspacy `hu_core_news_lg` | Production Hungarian lemmatization |
| **English NLP** | spaCy `en_core_web_lg` | English lemmatization |
| **LLM Providers** | Groq, OpenRouter, Gemini, 9Router, Cerebras, SambaNova | Multi-provider with runtime switching |
| **Embeddings** | Gemini `gemini-embedding-001`, Jina v3, BGE-M3 | Multi-provider, configurable dimensions |
| **Deployment** | Docker Compose (4 services) | Reproducible local deployment |
| **CI/CD** | GitHub Actions | Automated lint + test on push |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- At least one LLM API key (Gemini is free, recommended)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/bilingual-search.git
cd bilingual-search
cp .env.example .env
# Edit .env — add at least GEMINI_API_KEY
```

### 2. Start with Docker Compose (recommended)

```bash
docker compose up --build
```

This starts all 4 services:
- **PostgreSQL + pgvector** on port 5434
- **ETL Pipeline** (runs once, indexes all data)
- **Search API** on port 8000
- **Admin UI** on port 3000

### 3. Or run locally for development

```bash
# Start database
docker compose up -d postgres

# Run ETL pipeline
python -m bilingual_etl.scripts.main_etl

# Start API server
uvicorn search_api.main:app --reload --port 8000

# Start Admin UI
cd admin-ui && npm install && npm run dev
```

### 4. Access

| Service | URL |
|---------|-----|
| Admin Dashboard | http://localhost:5173 (dev) or http://localhost:3000 (Docker) |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

Default login: `admin` / `admin`

---

## API Endpoints

### Search
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/search/category` | Hybrid search over categories (R15) |
| `POST` | `/match/companies` | Match companies with partner boost (R16) |
| `POST` | `/search/single-company` | Search within a single company (R17) |
| `GET`  | `/search/suggest` | Autocomplete suggestions |

### RAG & AI
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ask` | RAG answering with citations (supports SSE streaming) |
| `POST` | `/agent/ask` | Search agent with tool-use pattern |

### Admin
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | JWT authentication |
| `GET/PUT` | `/admin/config/{key}` | CRUD for app_config |
| `GET` | `/admin/config/providers/availability` | Check provider status |
| `GET/POST` | `/admin/conversations/` | Conversation history CRUD |
| `POST` | `/admin/etl/start` | Start ETL from UI |
| `POST` | `/admin/etl/stop` | Stop ETL from UI |
| `GET` | `/admin/etl/progress` | ETL progress polling |
| `GET` | `/admin/analytics` | Search analytics |

### Monitoring
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (DB, vector index, BM25) |
| `GET` | `/admin/observability/traces` | LLM call traces |
| `POST` | `/evaluation/run` | Run MRR/NDCG evaluation |

---

## Project Structure

```
bilingual_etl/           # ETL pipeline (independent Docker service)
  extract/               # Source ingestion from data/*.json
  transform/             # HTML cleaning, narrative building, chunking
  enrichment/            # Translation, language detection, AI enrichment
  nlp/                   # Protected terms, lemmatization (huspacy + spaCy)
  load/                  # pgvector client, atomic swap, schema
  providers/             # Multi-provider: LLM, embedding, prompt store
  scripts/               # Entrypoints: main_etl.py, simulate_atomic_rollback.py

search_api/              # Search microservice + Admin API (independent Docker service)
  routers/               # 12 route modules (category, companies, rag, agent, ...)
  services/              # RRF fusion, language router, RAG, search agent, traces
  models/                # Pydantic request/response schemas

admin-ui/                # React + Vite admin panel (independent Docker service)
  src/pages/             # 17 page components (Dashboard, RAGChat, SearchTest, ...)
  src/api.js             # API client with JWT handling

tests/                   # 26 test files mirroring bilingual_etl/ and search_api/
docs/learning/           # 39 learning documents with PDF exports
```

---

## LLM Provider Configuration

Switch providers at runtime from the Admin UI — no code changes or redeployment needed.

| Provider | Free Tier | Speed | Setup |
|----------|-----------|-------|-------|
| **Gemini** | 15 RPM / 1M tokens/day | Medium | [Get API key](https://aistudio.google.com/apikey) |
| **Groq** | 30 RPM | Very Fast | [Get API key](https://console.groq.com) |
| **OpenRouter** | Free models available | Varies | [Get API key](https://openrouter.ai/keys) |
| **9Router** | Via OpenCode Free | Slow | `npm i -g 9router && 9router` |
| **Cerebras** | Free tier | Fastest | [Get API key](https://cloud.cerebras.ai) |
| **SambaNova** | Free tier | Fast | [Get API key](https://cloud.sambanova.ai) |
| **Custom OpenAI** | Self-hosted | Local | Point to any OpenAI-compatible URL |

---

## Learning Trail

This project includes **39 learning documents** covering every non-trivial concept implemented — from vector search fundamentals to RRF fusion to rate limiting patterns. Each document includes:

- Plain-language explanation with real-life analogies
- Code walkthrough with inline comments
- Interview-ready summary

See [`docs/learning/INDEX.md`](docs/learning/INDEX.md) for the full list.

---

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=bilingual_etl --cov=search_api

# Run specific test module
pytest tests/test_rag.py -v
```

26 test files covering ETL stages, search services, API endpoints, and provider integrations.

---

## Environment Variables

See [`.env.example`](.env.example) for all configuration options. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `GEMINI_API_KEY` | Recommended | Google Gemini (free, used for LLM + embeddings) |
| `GROQ_API_KEY` | Optional | Groq fast inference |
| `OPENROUTER_API_KEY` | Optional | OpenRouter multi-model access |
| `CEREBRAS_API_KEY` | Optional | Cerebras fastest inference |
| `SAMBANOVA_API_KEY` | Optional | SambaNova free tier |
| `JWT_SECRET` | Yes | Secret for admin JWT tokens |
| `RATE_LIMIT_RPM` | Optional | Requests per minute per IP (default: 60) |
| `CORS_ORIGINS` | Optional | Comma-separated allowed origins |
| `DB_POOL_MAX` | Optional | Max DB pool connections (default: 10) |

---

## Security & Production Hardening

| Layer | Measure |
|-------|---------|
| **Authentication** | JWT with ephemeral secret generation, 8h expiry, role-based authorization |
| **Brute-force protection** | Per-IP+username sliding window — 5 attempts, 5-minute lockout |
| **Input validation** | `max_length` on all query fields, `Literal` types for table names (prevents SQL injection) |
| **Admin endpoint auth** | Every `/admin/*` route requires valid JWT with `role=admin` |
| **Security headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy` |
| **Rate limiting** | Per-IP sliding window (configurable RPM), memory-leak-safe cleanup |
| **Request tracing** | `X-Request-ID` on every response, structured error responses with request ID |
| **CORS** | Configurable allowed origins via `CORS_ORIGINS` env var |
| **DB connection pooling** | `ThreadedConnectionPool` (2–10 connections, configurable via `DB_POOL_MAX`) |
| **Docker hardening** | Non-root `appuser` in all service containers, `.dockerignore` to exclude secrets |
| **Secret management** | `.env` gitignored, `.env.example` with safe defaults, no hardcoded credentials |

---

## Requirements Traceability

This project implements **26 requirements** from the client specification, with full traceability from requirement to implementation to test to UAT evidence. See [`SPEC.md`](SPEC.md) for the complete traceability table.

Key requirement areas:
- **R1-R14**: Data model, ETL pipeline, bilingual processing
- **R15-R17**: Search endpoints (categories, companies, single-company)
- **R18-R21**: Hybrid search, RRF fusion, language detection
- **R22-R23**: Multi-provider LLM and embedding abstraction
- **R24-R26**: Admin UI, system prompts, authentication

---

## Stats

| Metric | Count |
|--------|-------|
| Python source files | 81 |
| Python lines of code | ~7,800 |
| React/JS lines of code | ~3,000 |
| API endpoints | 24 |
| Admin UI pages | 17 |
| Test files | 26 |
| Learning documents | 39 |
| Docker services | 4 |
| LLM providers supported | 7 |
| Embedding providers | 3 |

---

## License

MIT
