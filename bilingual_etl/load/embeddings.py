"""
Embedding Generation (R9, vector path)

Generates embedding vectors for narrative/chunk text via the embedding
provider abstraction (R23). Adds batching and retry-with-backoff on top of
the raw provider — providers are thin API wrappers (bilingual_etl/providers/
embedding_provider.py); resilience against transient failures and free-tier
rate limits belongs at this layer instead of being duplicated inside every
provider class.

The embedding path always uses the RAW narrative/chunk text — never
lemmatized or protected-terms-masked. Embedding models are trained on
natural language, so masking would corrupt exactly the words the model
needs to understand meaning; that masking only applies to the separate BM25
path (bilingual_etl/nlp/lemmatizer.py).

Usage:
    vectors = embed_texts(["narrative one", "narrative two"])
"""

import hashlib
import time

from loguru import logger

from bilingual_etl.providers.embedding_provider import EmbeddingProvider, get_embedding_provider

DEFAULT_BATCH_SIZE = 50
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_cache_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS embedding_cache (
                text_hash TEXT PRIMARY KEY,
                embedding VECTOR,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()


def _lookup_cached(conn, hashes: list[str]) -> dict[str, list[float]]:
    if not hashes:
        return {}
    placeholders = ",".join(["%s"] * len(hashes))
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT text_hash, embedding::text FROM embedding_cache WHERE text_hash IN ({placeholders})",
            tuple(hashes),
        )
        result = {}
        for row in cur.fetchall():
            vec_str = row[1].strip("[]")
            result[row[0]] = [float(x) for x in vec_str.split(",")]
        return result


def _store_cached(conn, items: list[tuple[str, list[float]]]) -> None:
    if not items:
        return
    with conn.cursor() as cur:
        for text_hash, embedding in items:
            vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
            cur.execute(
                "INSERT INTO embedding_cache (text_hash, embedding) VALUES (%s, %s::vector) ON CONFLICT (text_hash) DO NOTHING",
                (text_hash, vec_literal),
            )
        conn.commit()


def _get_retry_after(error: Exception) -> float | None:
    resp = getattr(error, "response", None)
    if resp is None or resp.status_code != 429:
        return None
    retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass
    return None


def _embed_batch_with_retry(batch: list[str], provider: EmbeddingProvider) -> list[list[float]]:
    backoff = INITIAL_BACKOFF_SECONDS
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return provider.embed(batch)
        except Exception as e:
            last_error = e
            retry_after = _get_retry_after(e)
            wait = retry_after if retry_after else backoff
            logger.warning(
                f"Embedding batch failed (attempt {attempt}/{MAX_RETRIES}): {e}"
                + (f" | Retry-After: {retry_after}s" if retry_after else "")
            )
            if attempt < MAX_RETRIES:
                time.sleep(wait)
                backoff *= 2

    raise RuntimeError(f"Embedding batch failed after {MAX_RETRIES} attempts: {last_error}") from last_error


def embed_texts(
    texts: list[str],
    provider: EmbeddingProvider | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    cache_conn=None,
) -> list[list[float]]:
    if not texts:
        return []

    provider = provider or get_embedding_provider()

    if cache_conn:
        try:
            _ensure_cache_table(cache_conn)
        except Exception:
            cache_conn = None

    hashes = [_text_hash(t) for t in texts]
    cached = _lookup_cached(cache_conn, hashes) if cache_conn else {}
    cache_hits = sum(1 for h in hashes if h in cached)

    uncached_indices = [i for i, h in enumerate(hashes) if h not in cached]
    uncached_texts = [texts[i] for i in uncached_indices]

    if uncached_texts:
        new_embeddings: list[list[float]] = []
        num_batches = ((len(uncached_texts) - 1) // batch_size) + 1

        for i in range(0, len(uncached_texts), batch_size):
            batch = uncached_texts[i : i + batch_size]
            new_embeddings.extend(_embed_batch_with_retry(batch, provider))

        to_cache = []
        for idx, emb in zip(uncached_indices, new_embeddings):
            cached[hashes[idx]] = emb
            to_cache.append((hashes[idx], emb))

        if cache_conn and to_cache:
            try:
                _store_cached(cache_conn, to_cache)
            except Exception as e:
                logger.warning(f"Failed to write embedding cache: {e}")
    else:
        num_batches = 0

    results = [cached[h] for h in hashes]

    logger.info(
        f"Embeddings: {len(results)} total, {cache_hits} cached, "
        f"{len(uncached_texts)} computed across {num_batches} batch(es) "
        f"via provider={provider.name}"
    )
    return results
