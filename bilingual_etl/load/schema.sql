-- Bilingual AI Search Infrastructure — Database Schema
-- Requires: PostgreSQL 15+ with pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- category_vectors: one row per language per category
-- A category like "Forklift" gets two rows: one HU, one EN.
-- Each row stores:
--   - the narrative text (prose description)
--   - a vector embedding (for semantic/meaning search)
--   - BM25 tokens (for keyword search)
--   - metadata (AI enrichment fields like ai_type, status, etc.)
--   - a content hash (to skip reprocessing unchanged records)
-- ============================================================
CREATE TABLE IF NOT EXISTS category_vectors (
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

-- ============================================================
-- company_vectors: chunked company data, one row per chunk per language
-- A company profile is split into ≤500-word chunks.
-- Each chunk gets its own embedding and BM25 tokens.
-- is_highlighted = true means "Premium Partner" (gets a score boost in search).
-- ============================================================
CREATE TABLE IF NOT EXISTS company_vectors (
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

-- ============================================================
-- app_config: dynamic key-value config store
-- Stores which AI provider is active, system prompts for
-- translation/enrichment, auth credentials, etc.
-- Editable via the Admin UI without redeployment.
-- ============================================================
CREATE TABLE IF NOT EXISTS app_config (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Indexes
-- ============================================================

-- pgvector indexes: enable fast nearest-neighbor search on embeddings
-- Using HNSW (Hierarchical Navigable Small World) — faster than IVFFlat
-- for our dataset size, and doesn't require a training step.
CREATE INDEX IF NOT EXISTS idx_category_vectors_embedding
    ON category_vectors USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_company_vectors_embedding
    ON company_vectors USING hnsw (embedding vector_cosine_ops);

-- GIN indexes on BM25 tsvector columns: enable fast full-text keyword search
CREATE INDEX IF NOT EXISTS idx_category_bm25_hu ON category_vectors USING gin (bm25_tokens_hu);
CREATE INDEX IF NOT EXISTS idx_category_bm25_en ON category_vectors USING gin (bm25_tokens_en);
CREATE INDEX IF NOT EXISTS idx_company_bm25_hu  ON company_vectors USING gin (bm25_tokens_hu);
CREATE INDEX IF NOT EXISTS idx_company_bm25_en  ON company_vectors USING gin (bm25_tokens_en);

-- GIN index on metadata JSONB: enables fast filtering by metadata fields
CREATE INDEX IF NOT EXISTS idx_category_metadata ON category_vectors USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_company_metadata  ON company_vectors USING gin (metadata);

-- B-tree indexes on ID columns: fast lookups by category/company ID
CREATE INDEX IF NOT EXISTS idx_category_id ON category_vectors (category_id);
CREATE INDEX IF NOT EXISTS idx_company_id  ON company_vectors (company_id);
