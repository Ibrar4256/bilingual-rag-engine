"""
AI Enrichment (R5)

Generates 6 structured fields per category/company per language:
ai_type, status, add_words (SEO keywords), recommended_headline,
synthetic_questions, topic_suggestions.

Goes through the LLM provider abstraction (R22) and reads its system prompt
from the PromptStore (R24), same as translation. The LLM is asked to respond
with raw JSON; since LLMs sometimes wrap JSON in markdown code fences despite
instructions not to, the response is defensively unwrapped before parsing.

Usage:
    result = enrich("Ipari szivattyuk es alkatreszek gyartasa es forgalmazasa.")
    # {"ai_type": "...", "status": "OK", "add_words": [...], ...}
"""

from loguru import logger

from bilingual_etl.providers.guardrails import generate_with_guardrails
from bilingual_etl.providers.llm_provider import LLMProvider, get_llm_provider
from bilingual_etl.providers.prompt_store import PromptStore

REQUIRED_FIELDS = [
    "ai_type",
    "status",
    "add_words",
    "recommended_headline",
    "synthetic_questions",
    "topic_suggestions",
]

FIELD_TYPES = {
    "ai_type": str,
    "status": str,
    "add_words": list,
    "recommended_headline": str,
    "synthetic_questions": list,
    "topic_suggestions": list,
}


def _empty_enrichment(status: str = "REVIEW") -> dict:
    return {
        "ai_type": None,
        "status": status,
        "add_words": [],
        "recommended_headline": None,
        "synthetic_questions": [],
        "topic_suggestions": [],
    }


def enrich(
    text: str,
    llm: LLMProvider | None = None,
    prompt_store: PromptStore | None = None,
) -> dict:
    if not text:
        return _empty_enrichment(status="DELETE")

    llm = llm or get_llm_provider()
    prompt_store = prompt_store or PromptStore()

    system_prompt = prompt_store.get_enrichment_prompt()
    data, errors = generate_with_guardrails(
        llm, text, system_prompt=system_prompt,
        required_fields=REQUIRED_FIELDS, field_types=FIELD_TYPES,
    )

    if errors or data is None:
        logger.warning(f"Enrichment guardrail fallback: {errors}")
        return _empty_enrichment()

    result = {field: data.get(field) for field in REQUIRED_FIELDS}
    logger.info(f"Enriched text ({len(text)} chars) -> status={result['status']}")
    return result
