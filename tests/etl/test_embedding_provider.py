"""Tests for embedding provider abstraction (R23)."""

from unittest.mock import MagicMock, patch

import pytest

from bilingual_etl.providers.embedding_provider import (
    GeminiEmbedding,
    JinaEmbedding,
    get_embedding_provider,
)


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("JINA_API_KEY", "fake-jina-key")


class TestGeminiEmbedding:
    @patch("bilingual_etl.providers.embedding_provider.requests.post")
    def test_embed_single_text(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"embedding": {"values": [0.1] * 768}}
        )
        provider = GeminiEmbedding()
        result = provider.embed(["test text"])

        assert len(result) == 1
        assert len(result[0]) == 768
        assert provider.dimensions == 768

    @patch("bilingual_etl.providers.embedding_provider.requests.post")
    def test_embed_multiple_texts(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"embedding": {"values": [0.1] * 768}}
        )
        provider = GeminiEmbedding()
        result = provider.embed(["text one", "text two", "text three"])

        assert len(result) == 3
        assert mock_post.call_count == 3

    @patch("bilingual_etl.providers.embedding_provider.requests.post")
    def test_embed_single_convenience(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"embedding": {"values": [0.5] * 768}}
        )
        provider = GeminiEmbedding()
        result = provider.embed_single("test")

        assert len(result) == 768
        assert result[0] == 0.5

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiEmbedding()


class TestJinaEmbedding:
    @patch("bilingual_etl.providers.embedding_provider.requests.post")
    def test_embed_batch(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {
                "data": [
                    {"embedding": [0.2] * 1024},
                    {"embedding": [0.3] * 1024},
                ]
            }
        )
        provider = JinaEmbedding()
        result = provider.embed(["text a", "text b"])

        assert len(result) == 2
        assert len(result[0]) == 1024
        assert provider.dimensions == 1024
        assert mock_post.call_count == 1

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("JINA_API_KEY")
        with pytest.raises(ValueError, match="JINA_API_KEY"):
            JinaEmbedding()


class TestGetEmbeddingProvider:
    def test_get_by_name(self):
        provider = get_embedding_provider("gemini")
        assert isinstance(provider, GeminiEmbedding)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider("nonexistent")
