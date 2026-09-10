"""
Embedding Provider Abstraction (R23)

All embedding generation goes through this module — never call an embedding
API directly. Supports:
  - Google Gemini gemini-embedding-001 (primary, free)
  - Jina AI jina-embeddings-v3 (fallback, 10M free tokens)
  - Self-hosted BAAI/bge-m3 via sentence-transformers (offline fallback)

The active provider is read from the app_config DB table (set via Admin UI).
Embedding dimensionality varies by provider — the schema defaults to 768.

Usage:
    provider = get_embedding_provider()
    vectors = provider.embed(["text one", "text two"])
    # returns: list of lists of floats, e.g. [[0.1, 0.2, ...], [0.3, 0.4, ...]]
"""

import os
from abc import ABC, abstractmethod

import requests
from loguru import logger


class EmbeddingProvider(ABC):
    """Base interface — every backend implements this."""

    name: str = "base"
    dimensions: int = 768

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_single(self, text: str) -> list[float]:
        return self.embed([text])[0]


class GeminiEmbedding(EmbeddingProvider):
    """Google Gemini gemini-embedding-001 — free, configurable dims via MRL."""

    name = "gemini"
    dimensions = 768

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")
        self.model = "gemini-embedding-001"
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:embedContent?key={self.api_key}"
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            payload = {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": self.dimensions,
            }
            resp = requests.post(self.url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            embedding = data["embedding"]["values"]
            results.append(embedding)

        logger.info(
            f"Embedded {len(texts)} text(s) via provider=gemini "
            f"model={self.model} dims={self.dimensions}"
        )
        return results


class JinaEmbedding(EmbeddingProvider):
    """Jina AI jina-embeddings-v3 — 10M free tokens on signup."""

    name = "jina"
    dimensions = 1024

    def __init__(self):
        self.api_key = os.getenv("JINA_API_KEY", "")
        if not self.api_key:
            raise ValueError("JINA_API_KEY not set in environment")
        self.model = "jina-embeddings-v3"
        self.url = "https://api.jina.ai/v1/embeddings"

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        results = [item["embedding"] for item in data["data"]]
        logger.info(
            f"Embedded {len(texts)} text(s) via provider=jina "
            f"model={self.model} dims={self.dimensions}"
        )
        return results


class LocalBGEEmbedding(EmbeddingProvider):
    """Self-hosted BAAI/bge-m3 via sentence-transformers — zero API cost."""

    name = "local_bge_m3"
    dimensions = 1024

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for local embedding. "
                "Install with: pip install sentence-transformers"
            )
        logger.info("Loading BAAI/bge-m3 model (first run downloads ~2GB)...")
        self._model = SentenceTransformer("BAAI/bge-m3")

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        results = [emb.tolist() for emb in embeddings]
        logger.info(
            f"Embedded {len(texts)} text(s) via provider=local_bge_m3 "
            f"dims={self.dimensions}"
        )
        return results


class NineRouterEmbedding(EmbeddingProvider):
    """9Router — local AI router proxying OpenAI-compatible embedding endpoints."""

    name = "9router"
    dimensions = 768

    def __init__(self):
        self.api_key = os.getenv("NINE_ROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError("NINE_ROUTER_API_KEY not set in environment")
        base_url = os.getenv("NINE_ROUTER_URL", "http://localhost:20128")
        self.url = f"{base_url}/v1/embeddings"
        self.model = os.getenv("NINE_ROUTER_EMBED_MODEL", "text-embedding-3-small")

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model,
            "input": texts,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        results = [item["embedding"] for item in data["data"]]
        logger.info(
            f"Embedded {len(texts)} text(s) via provider=9router "
            f"model={self.model} dims={self.dimensions}"
        )
        return results


PROVIDERS = {
    "gemini": GeminiEmbedding,
    "jina": JinaEmbedding,
    "local_bge_m3": LocalBGEEmbedding,
    "9router": NineRouterEmbedding,
}


class TracedEmbeddingProvider(EmbeddingProvider):
    """Wraps any EmbeddingProvider to add observability tracing."""

    def __init__(self, inner: EmbeddingProvider):
        self._inner = inner
        self.name = inner.name
        self.dimensions = inner.dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            from search_api.services.llm_traces import traced_embed
            return traced_embed(self._inner, texts)
        except ImportError:
            return self._inner.embed(texts)


def get_embedding_provider(provider_name: str | None = None) -> EmbeddingProvider:
    if provider_name is None:
        provider_name = _get_active_provider_from_db()

    cls = PROVIDERS.get(provider_name)
    if cls is None:
        raise ValueError(
            f"Unknown embedding provider '{provider_name}'. "
            f"Available: {list(PROVIDERS.keys())}"
        )
    return TracedEmbeddingProvider(cls())


def _get_active_provider_from_db() -> str:
    try:
        from bilingual_etl.load.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value->>'active' FROM app_config WHERE key = 'embedding_provider'"
                )
                row = cur.fetchone()
                if row and row[0]:
                    return row[0]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Could not read embedding provider from DB: {e}. Defaulting to 'gemini'.")
    return "gemini"
