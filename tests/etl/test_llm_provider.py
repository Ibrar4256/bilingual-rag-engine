"""Tests for LLM provider abstraction (R22)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from bilingual_etl.providers.llm_provider import (
    GeminiLLM,
    GroqLLM,
    OpenRouterLLM,
    get_llm_provider,
)


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-openrouter-key")


class TestGeminiLLM:
    @patch("bilingual_etl.providers.llm_provider.requests.post")
    def test_generate_sends_correct_payload(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [
                    {"content": {"parts": [{"text": "Szia, jól vagyok."}]}}
                ]
            },
        )
        provider = GeminiLLM()
        result = provider.generate("Hello", system_prompt="Be helpful")

        assert result == "Szia, jól vagyok."
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(payload["contents"]) == 3
        assert payload["contents"][0]["role"] == "user"
        assert payload["contents"][1]["role"] == "model"

    @patch("bilingual_etl.providers.llm_provider.requests.post")
    def test_generate_without_system_prompt(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {
                "candidates": [{"content": {"parts": [{"text": "Hi"}]}}]
            }
        )
        provider = GeminiLLM()
        result = provider.generate("Hello")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert len(payload["contents"]) == 1
        assert result == "Hi"

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiLLM()


class TestGroqLLM:
    @patch("bilingual_etl.providers.llm_provider.requests.post")
    def test_generate_openai_format(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {
                "choices": [{"message": {"content": "Válasz"}}]
            }
        )
        provider = GroqLLM()
        result = provider.generate("Translate", system_prompt="Be a translator")

        assert result == "Válasz"
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["model"] == "openai/gpt-oss-120b"

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY")
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            GroqLLM()


class TestOpenRouterLLM:
    @patch("bilingual_etl.providers.llm_provider.requests.post")
    def test_generate_openai_format(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {
                "choices": [{"message": {"content": "Result"}}]
            }
        )
        provider = OpenRouterLLM()
        result = provider.generate("Hello")

        assert result == "Result"
        assert provider.name == "openrouter"

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY")
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            OpenRouterLLM()


class TestGetLLMProvider:
    def test_get_by_name(self):
        provider = get_llm_provider("gemini")
        assert isinstance(provider, GeminiLLM)

    def test_get_groq_by_name(self):
        provider = get_llm_provider("groq")
        assert isinstance(provider, GroqLLM)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider("nonexistent")
