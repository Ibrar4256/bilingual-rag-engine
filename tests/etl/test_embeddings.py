"""Tests for embedding generation (R9, vector path)."""

from unittest.mock import MagicMock, patch

import pytest

from bilingual_etl.load.embeddings import DEFAULT_BATCH_SIZE, MAX_RETRIES, embed_texts


def make_mock_provider(name: str = "test") -> MagicMock:
    provider = MagicMock()
    provider.name = name
    return provider


class TestEmbedTexts:
    def test_empty_list_returns_empty_without_calling_provider(self):
        provider = make_mock_provider()
        result = embed_texts([], provider=provider)
        assert result == []
        provider.embed.assert_not_called()

    def test_single_batch(self):
        provider = make_mock_provider()
        provider.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]

        result = embed_texts(["text one", "text two"], provider=provider, batch_size=50)

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        provider.embed.assert_called_once_with(["text one", "text two"])

    def test_splits_into_multiple_batches(self):
        provider = make_mock_provider()
        provider.embed.side_effect = [[[0.1]], [[0.2]], [[0.3]]]

        result = embed_texts(["a", "b", "c"], provider=provider, batch_size=1)

        assert result == [[0.1], [0.2], [0.3]]
        assert provider.embed.call_count == 3

    def test_uneven_batches(self):
        provider = make_mock_provider()
        provider.embed.side_effect = [[[0.1], [0.2]], [[0.3]]]

        result = embed_texts(["a", "b", "c"], provider=provider, batch_size=2)

        assert result == [[0.1], [0.2], [0.3]]
        assert provider.embed.call_args_list[0].args[0] == ["a", "b"]
        assert provider.embed.call_args_list[1].args[0] == ["c"]

    def test_default_batch_size_constant(self):
        assert DEFAULT_BATCH_SIZE == 50


class TestRetryWithBackoff:
    def test_retries_on_failure_then_succeeds(self):
        provider = make_mock_provider()
        provider.embed.side_effect = [Exception("rate limited"), [[0.1, 0.2]]]

        with patch("bilingual_etl.load.embeddings.time.sleep") as mock_sleep:
            result = embed_texts(["text"], provider=provider)

        assert result == [[0.1, 0.2]]
        assert provider.embed.call_count == 2
        mock_sleep.assert_called_once()

    def test_exhausts_retries_and_raises(self):
        provider = make_mock_provider()
        provider.embed.side_effect = Exception("persistent failure")

        with patch("bilingual_etl.load.embeddings.time.sleep"):
            with pytest.raises(RuntimeError, match="failed after"):
                embed_texts(["text"], provider=provider)

        assert provider.embed.call_count == MAX_RETRIES

    def test_backoff_doubles_each_attempt(self):
        provider = make_mock_provider()
        provider.embed.side_effect = [Exception("e1"), Exception("e2"), [[0.1]]]

        with patch("bilingual_etl.load.embeddings.time.sleep") as mock_sleep:
            embed_texts(["text"], provider=provider)

        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [2, 4]
