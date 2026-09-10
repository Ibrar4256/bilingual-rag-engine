# Client UAT Evidence README (Milestone 1)

This document is a client-facing evidence pack template for the following requests:

- ETL correctness + data quality observations
- AC evidence for hash skip, dual-path indexing, atomic swap, bilingual parity
- Live API + explicit RRF proof

Use this file as the final handover note and paste fresh evidence blocks under each section.

---

## 1) Current status (implementation vs evidence)

- **Implemented in code**: protected terms flow, dual path logic, atomic swap pattern, RRF endpoints, metadata exposure in UI, company/category narrative fixes.
- **Evidence still required for sign-off**: non-force rerun (`0 OpenAI calls`), DB snippets for dual-path, crash simulation run, live endpoint payload captures.

---

## 2) Evidence format required by client

Client expects **timestamped runtime proof** like:

`2026-04-08 18:47:55.799 | INFO | ... | Completed BM25 lemmatization`

So every section below includes:

- **What to capture**
- **Paste-ready example lines**
- **What you (Fiaz) still need to add**

---

## 3) ETL Data Observations response mapping

### 3.1 Missing AI fields + JSONB metadata visibility

**What to show**
- Category metadata contains `status`, `recommended_headline`, `topic_suggestions`.
- Company metadata contains pre-filtering fields (`service_models`, `logistics_capabilities`, `brands_carried`, etc.).

**Example evidence sources**
- UI inspector:
  - `6) Metadata`
  - `7) AI_enrichment`
- API response (`/search/category`, `/match/companies`) now includes `metadata` object.

**You need to add**
- 2 screenshots from UI (category + company) with visible metadata JSON.
- 1 API response sample per endpoint with metadata block expanded.

---

### 3.2 Bilingual parity / language isolation

**What to show**
- HU narrative and HU synthetic questions are language-aligned.
- BM25 built in language-specific branch.

**Example log lines**
- `Completed BM25 lemmatization`
- `Assigned BM25 tokens to language-specific field`

**You need to add**
- One HU sample row and one EN sample row from UI showing narrative + synthetic questions.

---

### 3.3 Context header formatting ([CÉG]/[PROFIL])

**What to show**
- Company chunk header uses localized tags for HU.

**Example log marker**
- `EVIDENCE_COMPANY_CHUNK_HEADER`

**You need to add**
- One chunk preview screenshot from company chunking table (HU row).

---

### 3.4 Company synthetic questions appended before chunking

**What to show**
- Questions appended to assembled narrative text before chunking/vectorization.

**Example log marker**
- `EVIDENCE_COMPANY_SYNTHETIC_QUESTIONS_APPEND`

**You need to add**
- One sample narrative/chunk text where questions block is visible.

---

### 3.5 Narrative structure/order fix

**What to show**
- Company narrative now keeps long category list near the end.
- Corporate fields are natural sentences (not only robotic key-value dump).

**You need to add**
- Before/after screenshot from inspector narrative panel (1 category + 1 company).

---

### 3.6 Deterministic ai_type bug

**What to show**
- ai_type normalization no longer keeps raw `deterministic`.

**You need to add**
- One category payload example where ai_type is normalized.

---

### 3.7 Company main profile selection logic

**What to show**
- Main profile is selected by scoring against activities/services/description (not pure alphabetical).

**You need to add**
- 1-2 company examples where selected profile is reasonable.

---

## 4) AC evidence pack (must provide)

### AC-1: Hash-based change detection (0 OpenAI calls on unchanged rerun)

**Required run sequence**
1. Force run:
   - `python -m bilingual_etl.scripts.main_etl --force-enrichment`
2. Immediate non-force run:
   - `python -m bilingual_etl.scripts.main_etl`

**Expected markers (non-force run)**
- `Skipping category enrichment; base hash unchanged`
- `Skipping company language rows; content hash unchanged`
- `Category enrichment skipped; no rows require LLM processing (OpenAI calls = 0)`
- `EVIDENCE_AC_HASH_SKIP_CATEGORY`
- `EVIDENCE_AC_HASH_SKIP_COMPANY`

**Captured proof (latest non-force run)**
- `2026-04-08 19:44:12.910 | INFO     | bilingual_etl.pipeline:_transform_categories_node:536 - Skipping category enrichment; base hash unchanged`
- `2026-04-08 19:44:12.923 | INFO     | bilingual_etl.pipeline:_transform_categories_node:721 - Category enrichment skipped; no rows require LLM processing (OpenAI calls = 0)`
- `2026-04-08 19:44:12.926 | INFO     | bilingual_etl.load.pgvector_client:upsert_category_vectors:395 - No category vector changes detected; skipping upsert`
- `2026-04-08 19:44:13.780 | INFO     | bilingual_etl.pipeline:_transform_companies_node:1305 - Skipping company language rows; source hash unchanged`
- `2026-04-08 19:44:15.287 | INFO     | bilingual_etl.load.pgvector_client:upsert_company_vectors:520 - No company vector changes detected; skipping upsert`
- `2026-04-08 19:44:15.333 | INFO     | __main__:main:109 - Full ETL (clean + vectors) finished successfully`

**Interpretation**
- Category side now has explicit `OpenAI calls = 0` evidence on unchanged rerun.
- Company side skipped by `source hash unchanged` and did not upsert changed rows.

---

### AC-2: Protected terms ("Bunting") proof

**Expected log pattern**
- `Applied protected term masking`
- `Completed BM25 lemmatization`
- `Unmasked lemmatized BM25 tokens`

**Example from current runtime.log**
- `2026-04-08 12:54:46.918 | INFO | ... | Completed BM25 lemmatization`
- `2026-04-08 12:54:46.918 | INFO | ... | Unmasked lemmatized BM25 tokens`

**You need to add**
- DB snippet where `bm25_tokens_hu` or `bm25_tokens_en` includes `bunting`.

---

### AC-3: Dual-path indexing proof

**Expected markers**
- `EVIDENCE_AC_DUAL_PATH_CATEGORY`
- `EVIDENCE_AC_DUAL_PATH_COMPANY`

**DB proof query (2-3 rows)**
```sql
SELECT
  company_id,
  language,
  LEFT(narrative_templates, 240) AS vector_text_preview,
  LEFT(COALESCE(bm25_tokens_hu::text, bm25_tokens_en::text, ''), 240) AS bm25_tokens_preview
FROM company_vectors
ORDER BY created_at DESC
LIMIT 3;
```

```sql
SELECT
  category_id,
  language,
  LEFT(narrative_templates, 240) AS vector_text_preview,
  LEFT(COALESCE(bm25_tokens_hu::text, bm25_tokens_en::text, ''), 240) AS bm25_tokens_preview
FROM category_vectors
ORDER BY updated_at DESC
LIMIT 3;
```

**You need to add**
- Paste both query outputs.

---

### AC-4: Atomic swap / rollback safety

**Expected success lines (already visible)**
- `Executing company atomic swap in PostgreSQL`
- `Company atomic swap executed`
- `Executing category atomic swap in PostgreSQL`
- `Category atomic swap executed`

**Example from current runtime.log**
- `2026-04-08 12:56:40.725 | INFO | ... | Executing company atomic swap in PostgreSQL`
- `2026-04-08 12:56:40.804 | INFO | ... | Company atomic swap executed`

**You need to add (still pending for formal sign-off)**
- One controlled failure simulation log + post-check query proving rollback/no partial rows.

**Automated simulation command (new)**
- `python -m bilingual_etl.scripts.simulate_atomic_rollback`

**Expected markers from simulation run**
- `EVIDENCE_ATOMIC_SWAP_SIMULATION_START`
- `EVIDENCE_ATOMIC_SWAP_SIMULATED_FAILURE_CAUGHT`
- `EVIDENCE_ATOMIC_SWAP_ROLLBACK_RESULT` (must show `rollback_ok=true`)
- `EVIDENCE_ATOMIC_SWAP_SIMULATION_DONE`

---

### AC-5: Bilingual parity and end-to-end execution

**Expected proof**
- HU/EN rows generated for category/company vectors
- ETL completed successfully

**You need to add**
- 1 HU and 1 EN sample from UI with same concept parity.

---

### AC-6: Live API + explicit RRF scoring

**Expected proof**
- Endpoints:
  - `/search/category`
  - `/match/companies`
  - `/search/single-company`
- Response has:
  - `retrieval_mode: "hybrid_rrf"`
  - metadata/context fields

**Expected log marker**
- `EVIDENCE_API_RRF_MERGE`

**You need to add**
- 3 request payloads + 3 response payloads (one per endpoint).
- At least one case where both BM25 and vector candidates are present in fusion context.

---

## 5) Company dify_config quality control (new)

Now added in pipeline:

- Advanced merged company dify config (v2):
  - `negative_keywords`, `tier_*_params`, `questions`, `synthetic_questions`, `topic_suggestions`, `recommended_headline`, `coverage`, etc.
- Language fallback fetch when target-language category config is missing.
- Strict validator + warnings:
  - `EVIDENCE_COMPANY_DIFY_CONFIG_BUILD`
  - `EVIDENCE_COMPANY_DIFY_CONFIG_VALIDATION`

**You need to add**
- 1-2 companies where `coverage.resolution_rate` is shown.
- 1 warning case (if any) to show QA control is active.

**Captured warning example (from latest non-force run)**
- `2026-04-08 19:44:13.778 | WARNING  | bilingual_etl.pipeline:_transform_companies_node:1133 - Company category labels did not resolve to category_ids; company dify_config and category_attribute_injection will stay empty (check category ETL for this language and DATABASE_URL during company transform).`

This line is useful as transparent QA evidence. It also explains why some companies show empty `dify_config`: unresolved category labels mean no category-linked config can be aggregated.

---

## 6) Final checklist before sending to client

- [ ] Non-force rerun log with `0 OpenAI calls` evidence markers
- [ ] Protected terms DB snippet (`bunting` visible in BM25 tokens)
- [ ] Dual-path DB snippets (category + company)
- [ ] Crash simulation evidence (rollback-safe)
- [ ] 3 live API request/response payload sets with `hybrid_rrf`
- [ ] UI screenshots:
  - [ ] Metadata section
  - [ ] AI_enrichment with `status`, `recommended_headline`, `topic_suggestions`
  - [ ] Chunking header ([CÉG]/[PROFIL])

---

## 7) Notes for log extraction

Use `logs/runtime.log` and search by these keys:

- `EVIDENCE_AC_HASH_SKIP_CATEGORY`
- `EVIDENCE_AC_HASH_SKIP_COMPANY`
- `EVIDENCE_AC_DUAL_PATH_CATEGORY`
- `EVIDENCE_AC_DUAL_PATH_COMPANY`
- `EVIDENCE_COMPANY_SYNTHETIC_QUESTIONS_APPEND`
- `EVIDENCE_COMPANY_CHUNK_HEADER`
- `EVIDENCE_COMPANY_DIFY_CONFIG_BUILD`
- `EVIDENCE_COMPANY_DIFY_CONFIG_VALIDATION`
- `EVIDENCE_CATEGORY_DIFY_CONFIG_VALIDATION`
- `EVIDENCE_API_RRF_MERGE`

---

Prepared for: **Client UAT / Leadership Demo evidence handover**
