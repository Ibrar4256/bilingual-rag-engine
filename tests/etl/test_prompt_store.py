"""Tests for prompt store (R24)."""

from unittest.mock import MagicMock, patch

import pytest

from bilingual_etl.providers.prompt_store import (
    DEFAULT_ENRICHMENT_PROMPT,
    DEFAULT_TRANSLATION_PROMPT,
    PromptStore,
)


class TestPromptStore:
    @patch("bilingual_etl.providers.prompt_store.get_connection")
    def test_loads_prompts_from_db(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("prompt_translation", "Custom translation prompt"),
            ("prompt_enrichment", "Custom enrichment prompt"),
        ]
        mock_conn.return_value.__enter__ = lambda s: s
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

        store = PromptStore()
        assert store.get_translation_prompt() == "Custom translation prompt"
        assert store.get_enrichment_prompt() == "Custom enrichment prompt"

    @patch("bilingual_etl.providers.prompt_store.get_connection")
    def test_falls_back_to_defaults_on_db_error(self, mock_conn):
        mock_conn.side_effect = Exception("DB unavailable")

        store = PromptStore()
        assert store.get_translation_prompt() == DEFAULT_TRANSLATION_PROMPT
        assert store.get_enrichment_prompt() == DEFAULT_ENRICHMENT_PROMPT

    @patch("bilingual_etl.providers.prompt_store.get_connection")
    def test_falls_back_to_defaults_when_empty(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.return_value.__enter__ = lambda s: s
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

        store = PromptStore()
        assert store.get_translation_prompt() == DEFAULT_TRANSLATION_PROMPT
        assert store.get_enrichment_prompt() == DEFAULT_ENRICHMENT_PROMPT
