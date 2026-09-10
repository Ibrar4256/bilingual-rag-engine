# REQUIREMENTS.md

Source documents:
- `docs/requirements/Business needs for ETL pipeline and search (1).pdf` (4 pages)
- `docs/requirements/Request for Quotation_ AI Search Infrastructure (ETL Pipeline + Search API) (1) (1).pdf` (14 pages)
- `docs/requirements/Technical Specification_ Bilingual AI Search Infrastructure (ETL Pipeline + Search API).pdf` (3 pages)
- `docs/Client_UAT_Evidence_README.md` (UAT evidence template, Milestone 1)
- `data/*.json` (3 dataset exports)

Client: A Hungarian B2B matchmaking/RFQ platform. Freemium model; suppliers pay for "Premium Partnership" placement boost.

---

## 1. Functional Requirements

**ETL Pipeline**

- **R1** — Ingest ~38,000+ B2B categories and ~5,000–10,000 company profiles from internal PostgreSQL source data.
- **R2** — Clean HTML out of source descriptions (BeautifulSoup — explicitly NOT via LLM).
- **R3** — Bidirectional Hungarian↔English translation for whichever language is missing per record, preserving technical terms/brand names. Provider-agnostic — runs through the multi-provider LLM abstraction (R22).
- **R4** — Automatic source-language detection (langdetect).
- **R5** — AI enrichment per category/company per language, producing 6 fields: `ai_type` (7-level classification — only 1 of 7 levels is documented: `GÉP_ÉS_BERENDEZÉS`), `status` (OK/REVIEW/DELETE), SEO keywords (`add_words`/`hirdetesi_kulcsszavak`), `recommended_headline`, `synthetic_questions` (3–5 buyer-facing), `topic_suggestions` (data-quality flags). Provider-agnostic — runs through the multi-provider LLM abstraction (R22).
- **R6** — Generate a "Narrative Template" per language: natural-language prose (not a keyword/JSON dump); category lists ordered near the end; corporate fields rendered as sentences.
- **R7** — Company chunking: ≤500 words/chunk, each chunk prefixed with a bilingual context header (`[CÉG:]/[COMPANY:]` + `[PROFIL:]/[PROFILE:]`); synthetic questions appended to the narrative before chunking.
- **R8** — "Protected Terms" pass: mask brand names/technical codes (e.g. "Bunting", "ISO-9001") via whitelist + regex before lemmatization, unmask after.
- **R9** — Dual-path indexing per record per language: (a) raw narrative → embedding vector via the multi-provider embedding abstraction (R23); (b) lemmatized tokens (huspacy `hu_core_news_lg` / spaCy `en_core_web_lg`) → PostgreSQL `tsvector` BM25 fields.
- **R10** — Hash-based change detection: skip re-translation/re-enrichment/re-embedding for unchanged records/languages.
- **R11** — Atomic Swap: transactional DELETE+INSERT per update so a crash mid-update leaves no partial rows.
- **R12** — Schema: `category_vectors` (category_id, language, narrative, embedding vector(1536), bm25_tokens_hu, bm25_tokens_en, metadata JSONB, content_hash, updated_at) and `company_vectors` (company_id, language, chunk_index, embedding, content_chunk, bm25_tokens_hu/en, metadata JSONB, is_highlighted, created_at), each with pgvector + GIN + B-tree indexes.

**Search API**

- **R13** — FastAPI hybrid search: BM25 (language-routed) + vector similarity, fused via Reciprocal Rank Fusion (RRF, k=60 default) — explicitly not a weighted average.
- **R14** — Bilingual RRF weighting: vector full weight, primary-language BM25 full weight, secondary-language BM25 weighted 0.5.
- **R15** — `POST /search/category` — category identification for chatbot pre-qualification; returns `ai_type` + metadata.
- **R16** — `POST /match/companies` — RFQ-to-supplier matching; JSONB pre-filters (location, logistics); Partner Boost ×1.15 for `is_highlighted` companies; aggregates best chunk per company.
- **R17** — `POST /search/single-company` — whitelabel search scoped to one `company_id`, for partner-site embedding.
- **R18** — Health-check endpoint verifying DB, vector index, BM25, and API connectivity.
- **R19** — Cross-language fallback: if in-language results fall below a relevance threshold, retry in the other language.
- **R20** — API responses include `detected_language`, `response_time_ms`; search responses include `retrieval_mode: "hybrid_rrf"` and metadata/context blocks.
- **R21** — Dockerize ETL, Search API, and Admin UI as independent services + `docker-compose.yml` for local dev with Postgres+pgvector.

**Multi-Provider AI Abstraction**

- **R22** — LLM provider abstraction for text generation (translation + AI enrichment): support Groq, OpenRouter, and Google Gemini as selectable backends behind a unified interface. Active provider is chosen at runtime via the Admin UI (R25) with a configured default. Each call logs which provider actually served it.
- **R23** — Embedding provider abstraction for vector generation: support Google Gemini (`gemini-embedding-001`, primary), Jina AI (`jina-embeddings-v3`, fallback), and self-hosted `sentence-transformers` (BAAI/bge-m3, offline fallback). Active provider selected via Admin UI. Embedding dimensionality varies by provider — schema uses a dimension that accommodates the active provider (configurable).
- **R24** — Dynamic system prompts: the prompts used for translation (R3) and AI enrichment (R5) are stored in the database and editable via the Admin UI (R25), not hardcoded in source. Changes take effect on the next ETL run without redeployment.

**Admin UI**

- **R25** — React + Vite admin panel: dropdown to select active LLM provider (R22) and embedding provider (R23) with a visible default; a text editor for each system prompt (translation, enrichment) with save/reset; display of current provider status and last-used metadata. Protected by basic username/password authentication.
- **R26** — Basic auth on the Admin UI: username/password login wall; credentials stored hashed in the database or env config; session/token-based after login.

---

## 2. Non-Functional Requirements

| Area | Requirement | Note |
|---|---|---|
| Performance | `/search/category` p95 < 500ms | consistent across docs |
| Performance | Company match latency | **conflict**: RFQ says p99 < 3s, Business Needs says p99 < 5000ms |
| Performance | Health check < 50ms | |
| Performance | DB pool min 5 / max 20 | |
| Accuracy | ETL success rate | **conflict**: Business Needs ≥85%, RFQ 97–99% |
| Accuracy | Translation quality > 95%, language detection > 95%, protected-terms preservation 100% | consistent |
| Accuracy | Search accuracy | ranges differ slightly across docs, roughly 88–96% |
| Cost | Original RFQ estimated ~$31 first run / ~$1–2.60/day with OpenAI. Actual cost now ≈ $0 using free-tier providers (Groq/OpenRouter/Gemini) | Updated per §5a decisions |
| Delivery | 7 weeks from contract signing | RFQ's own deadline/contact fields are unfilled placeholders |
| Deployment | Dockerized, docker-compose for local dev | **no production target specified** (cloud host, orchestration, CI/CD) |
| Documentation | README, OpenAPI/Swagger, bilingual processing guide, schema docs, pytest suite | |
| Security/Compliance | **Search API**: no auth (local-only). **Admin UI**: basic auth (username/password) per R26 | Search API gap flagged in §3; Admin UI auth decided in §5a |

---

## 3. Ambiguous, Missing, or Contradictory Requirements

1. **Biggest open question**: `Client_UAT_Evidence_README.md` describes an already-implemented, already-running system (`bilingual_etl` package, live Postgres tables, live API, real timestamped log lines from a "Milestone 1" run) with specific evidence still owed for client sign-off. **No source code exists anywhere in this project directory** — only `data/` and `docs/`. Unclear whether: (a) existing code lives in another repo/location that should be located and brought in, (b) this is a ground-up rebuild that must reproduce that exact implementation to satisfy the UAT template, or (c) something else entirely.
2. Project folder is named "Bilingual," but every document and the dataset point to **Hungarian + English**, not Arabic — needs confirming.
3. RFQ's submission deadline (`[DATE]`) and contact email (`[Your Email]`) are unfilled placeholders — is there an actual signed contract/deadline, or is 7 weeks just a working target?
4. Dataset scale mismatch: requirements cite 5,000–10,000 companies / 35,000–38,000+ categories; the actual sample files contain only 471 companies and 3,000 categories. Filename says "_sample_" — is `data/` a subset, and is the real source a live internal PostgreSQL DB we need separate access to?
5. Contradiction: Business Needs p.3 says data comes "exclusively from internal PostgreSQL databases," but p.2 also mentions "scraped web content" feeding company matching — is scraped data in scope?
6. `ai_type` "7-level classification" — only 1 of 7 levels is named anywhere (`GÉP_ÉS_BERENDEZÉS`). Need the full taxonomy from the client, or design one?
7. Cross-language fallback relevance threshold (R19) — value never specified.
8. RRF `k` parameter called "configurable" with no config mechanism described (env var? DB config? API param?).
9. Company-match latency target conflicts (see NFR table).
10. ETL success-rate target conflicts (see NFR table).
11. No auth/rate-limiting on an API that serves external partner chatbots — intentional (trusted internal network) or a gap to design in?
12. No production deployment target specified — only local docker-compose.
13. Business Needs PDF p.4, "Acceptance Criterias" section, ends immediately after the heading with no visible content — possibly a cut-off page.

---

## 4. Dataset Summary

Three JSON exports in `data/`, all Hungarian-language content (no Arabic detected):

| File | Size | Structure | Records | Role |
|---|---|---|---|---|
| `companies_data_for_vectors_sample_2026_03_11.json` | 34MB | flat array | 471 | Primary company source for embedding |
| `category_company_data.json` | 9.8MB | dict `{category, company}` wrapper | 1,080 categories / 60 companies | Smaller joined snapshot — looks stale/test (low ID overlap with the other two files) |
| `categories_export_2026_04_14T11_17_15Z.json` | 6.3MB | flat array | 3,000 | Canonical category taxonomy export |

**Data quality issues found:**
- `address` empty in **all 471** company records.
- `description` null/empty in **34%** of companies — the field most likely to be embedded.
- List-type fields inconsistently encoded: some as stringified JSON (`brands`, `certificates`, `services`), others as native arrays (`target_audience`, `logistics_capabilities`) — same conceptual type, two encodings.
- Numeric fields (`nr_employees`, `year_founded`, `registered_capital`, `profit_after_tax`) stored as strings.
- Category enrichment fields mostly sparse: `keywords` null in 98%, `synonyms` empty in 91% of the 3,000-category export.
- Dataset drift: only 10/60 company IDs and 225/1,080 category IDs in `category_company_data.json` overlap with the other two files.

---

## 5a. Decisions (resolving Section 3 ambiguities)

| # | Ambiguity | Decision |
|---|---|---|
| 1 | Prior implementation described in UAT README but no code exists here | Build fresh in this project. UAT README is deferred — it becomes the reference for testing/evidence once the build exists, not a spec to reverse-engineer now. |
| 2 | Hungarian/English vs "Bilingual" folder name | Confirmed Hungarian + English. |
| 4 | Dataset scale (471/3,000 records vs 5,000-10,000/38,000+ cited) | Use `data/` as-is as the full working dataset. Docs' larger numbers are future/target scale, not what we ingest now. |
| 3, 9, 10 | Unfilled RFQ deadline/contact; conflicting latency (3s vs 5s) and accuracy (85% vs 97-99%) targets | Use the stricter number wherever docs disagree (p99 < 3s, ETL success ≥ 97%, etc.). No hard delivery deadline — 7 weeks is a working guideline only. |
| Deployment | No production target specified | Local/Docker only via docker-compose. No cloud deployment in scope. |
| Scope | Must-have vs nice-to-have for v1 | Everything in Section 1 (R1-R21) is must-have for v1 — dataset is small enough (471/3,000 records) that deferring pieces isn't necessary. |
| Coding mode | N/A | Claude implements directly; user studies via `docs/learning/` trail rather than writing code by hand. |
| AI providers | Client docs mandated OpenAI; user opts for free alternatives instead | Use Groq / OpenRouter / Gemini for LLM (text generation); Gemini / Jina / self-hosted bge-m3 for embeddings. Build a provider-abstraction layer so any can be swapped via Admin UI dropdown. Code stays provider-agnostic. |
| Embeddings | Client docs mandated OpenAI `text-embedding-3-small` (1536 dims) | Primary: Gemini `gemini-embedding-001` (configurable dims, free). Fallback: Jina `jina-embeddings-v3` (1024 dims, 10M free tokens). Offline fallback: self-hosted BAAI/bge-m3 (1024 dims). Schema dimension is configurable (not hardcoded to 1536). |
| Admin UI | Not in original client requirements | New scope: React + Vite admin panel for provider selection + system prompt editing. Protected by basic auth. Added as R25/R26. |
| `is_highlighted` source (R16 Partner Boost) | No source field is documented as driving "Premium Partnership" status. `signal_lamp` (piros/sárga/zöld) exists in the company data but most plausibly represents a business/credit-health rating from the Hungarian company registry, not a subscription tier — assuming it means "premium" would likely be wrong. | Default `is_highlighted = false` for all companies in the ETL (matches the schema's own default). Flag for the client: what field/process actually marks a company as a paying Premium Partner? |

Items **5, 6, 7, 8, 11, 12, 13** from Section 3 remain open (no client answer available) and are carried into SPEC.md as explicit assumptions to flag if they turn out to matter (e.g. the missing 6 of 7 `ai_type` levels, the unspecified fallback threshold, the "scraped web content" contradiction).

---

## 5. UAT Evidence Format (from `Client_UAT_Evidence_README.md`)

- **Proof format**: timestamped runtime log lines, loguru-style: `YYYY-MM-DD HH:MM:SS.mmm | LEVEL | module:function:line - message`, searchable in `logs/runtime.log` by named `EVIDENCE_*` markers.
- **Per-requirement evidence** (6 Acceptance Criteria, AC-1..AC-6):
  - AC-1: non-force rerun log showing `0 OpenAI calls` (hash-skip proof).
  - AC-2: DB snippet showing a protected term (e.g. "bunting") surviving lemmatization in `bm25_tokens_*`.
  - AC-3: DB query output (2–3 rows) showing both vector-path and BM25-path columns populated per record.
  - AC-4: atomic-swap success log + a controlled-failure/rollback simulation proving no partial rows.
  - AC-5: one Hungarian + one English sample of the same concept, showing narrative/question parity.
  - AC-6: 3 request/response payload pairs (one per endpoint) showing `retrieval_mode: "hybrid_rrf"`.
- **Supporting artifacts**: UI screenshots (metadata panel, AI-enrichment fields, chunk header), `dify_config` quality-control examples plus one warning case.
- **Sign-off structure**: a checklist (README §6) of unchecked boxes to be ticked off with pasted evidence.
- **Folder/naming convention**: not explicitly defined in the README itself beyond `logs/runtime.log` — we will need to define a `uat-evidence/` convention in SPEC.md, consistent with this format, since the client hasn't dictated one.

**Every acceptance criterion written in SPEC.md (Phase 1) must be satisfiable by this exact evidence format** — timestamped log lines with `EVIDENCE_*` markers, DB query snippets, and request/response payload captures — not a custom test-report format.
