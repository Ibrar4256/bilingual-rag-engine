"""Tests for translation (R3)."""

from unittest.mock import MagicMock

import pytest

from bilingual_etl.enrichment.translator import other_language, translate


def make_mock_llm(response_text: str) -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = response_text
    return llm


def make_mock_prompt_store(translation_prompt: str = "Translate accurately.") -> MagicMock:
    store = MagicMock()
    store.get_translation_prompt.return_value = translation_prompt
    return store


class TestTranslate:
    def test_hu_to_en(self):
        llm = make_mock_llm("Industrial pumps manufacturer.")
        store = make_mock_prompt_store()

        result = translate("Ipari szivattyugyarto.", "hu", "en", llm=llm, prompt_store=store)

        assert result == "Industrial pumps manufacturer."
        llm.generate.assert_called_once()
        call_args = llm.generate.call_args
        assert "Hungarian" in call_args.args[0]
        assert "English" in call_args.args[0]
        assert call_args.kwargs["system_prompt"] == "Translate accurately."

    def test_en_to_hu(self):
        llm = make_mock_llm("Ipari szivattyugyarto.")
        store = make_mock_prompt_store()

        result = translate("Industrial pumps manufacturer.", "en", "hu", llm=llm, prompt_store=store)

        assert result == "Ipari szivattyugyarto."
        call_args = llm.generate.call_args
        assert "English" in call_args.args[0]
        assert "Hungarian" in call_args.args[0]

    def test_empty_text_returns_empty_without_calling_llm(self):
        llm = make_mock_llm("should not be used")
        store = make_mock_prompt_store()

        result = translate("", "hu", "en", llm=llm, prompt_store=store)

        assert result == ""
        llm.generate.assert_not_called()

    def test_uses_prompt_store_translation_prompt(self):
        llm = make_mock_llm("output")
        store = make_mock_prompt_store(translation_prompt="Custom translation instructions.")

        translate("input text", "hu", "en", llm=llm, prompt_store=store)

        assert llm.generate.call_args.kwargs["system_prompt"] == "Custom translation instructions."


class TestMarkdownStripping:
    def test_strips_bold_markers(self):
        llm = make_mock_llm("**compressor**")
        store = make_mock_prompt_store()

        result = translate("kompresszor", "hu", "en", llm=llm, prompt_store=store)

        assert result == "compressor"
        assert "*" not in result

    def test_strips_bold_within_longer_text(self):
        llm = make_mock_llm("This is a **compressor** and a pump.")
        store = make_mock_prompt_store()

        result = translate("text", "hu", "en", llm=llm, prompt_store=store)

        assert result == "This is a compressor and a pump."

    def test_plain_text_unaffected(self):
        llm = make_mock_llm("Industrial pumps manufacturer.")
        store = make_mock_prompt_store()

        result = translate("text", "hu", "en", llm=llm, prompt_store=store)

        assert result == "Industrial pumps manufacturer."


class TestOtherLanguage:
    def test_hu_flips_to_en(self):
        assert other_language("hu") == "en"

    def test_en_flips_to_hu(self):
        assert other_language("en") == "hu"

    def test_unsupported_language_raises(self):
        with pytest.raises(ValueError, match="Unsupported language"):
            other_language("fr")
