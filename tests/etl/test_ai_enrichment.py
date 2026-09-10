"""Tests for AI enrichment (R5)."""

import json
from unittest.mock import MagicMock

from bilingual_etl.enrichment.ai_enrichment import REQUIRED_FIELDS, enrich


def make_mock_llm(response_text: str) -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = response_text
    return llm


def make_mock_prompt_store(enrichment_prompt: str = "Analyze this.") -> MagicMock:
    store = MagicMock()
    store.get_enrichment_prompt.return_value = enrichment_prompt
    return store


VALID_RESPONSE = {
    "ai_type": "GÉP_ÉS_BERENDEZÉS",
    "status": "OK",
    "add_words": ["pumps", "industrial", "ISO 9001"],
    "recommended_headline": "Industrial Pump Manufacturer",
    "synthetic_questions": ["What pumps do you offer?", "Are parts available?"],
    "topic_suggestions": ["Add pricing information."],
}


class TestEnrich:
    def test_valid_json_response(self):
        llm = make_mock_llm(json.dumps(VALID_RESPONSE))
        store = make_mock_prompt_store()

        result = enrich("Some company description.", llm=llm, prompt_store=store)

        assert result == VALID_RESPONSE
        assert set(result.keys()) == set(REQUIRED_FIELDS)

    def test_response_wrapped_in_markdown_fence(self):
        fenced = f"```json\n{json.dumps(VALID_RESPONSE)}\n```"
        llm = make_mock_llm(fenced)
        store = make_mock_prompt_store()

        result = enrich("Some company description.", llm=llm, prompt_store=store)

        assert result == VALID_RESPONSE

    def test_response_wrapped_in_plain_fence(self):
        fenced = f"```\n{json.dumps(VALID_RESPONSE)}\n```"
        llm = make_mock_llm(fenced)
        store = make_mock_prompt_store()

        result = enrich("Some company description.", llm=llm, prompt_store=store)

        assert result == VALID_RESPONSE

    def test_invalid_json_falls_back_to_review(self):
        llm = make_mock_llm("This is not JSON at all.")
        store = make_mock_prompt_store()

        result = enrich("Some company description.", llm=llm, prompt_store=store)

        assert result["status"] == "REVIEW"
        assert result["add_words"] == []

    def test_missing_fields_still_returns_present_ones(self):
        partial = {"ai_type": "GÉP_ÉS_BERENDEZÉS", "status": "OK"}
        llm = make_mock_llm(json.dumps(partial))
        store = make_mock_prompt_store()

        result = enrich("Some company description.", llm=llm, prompt_store=store)

        assert result["ai_type"] == "GÉP_ÉS_BERENDEZÉS"
        assert result["status"] == "OK"
        assert result["add_words"] is None

    def test_empty_text_returns_delete_status_without_calling_llm(self):
        llm = make_mock_llm("should not be used")
        store = make_mock_prompt_store()

        result = enrich("", llm=llm, prompt_store=store)

        assert result["status"] == "DELETE"
        llm.generate.assert_not_called()

    def test_uses_prompt_store_enrichment_prompt(self):
        llm = make_mock_llm(json.dumps(VALID_RESPONSE))
        store = make_mock_prompt_store(enrichment_prompt="Custom enrichment instructions.")

        enrich("Some text", llm=llm, prompt_store=store)

        assert llm.generate.call_args.kwargs["system_prompt"] == "Custom enrichment instructions."
