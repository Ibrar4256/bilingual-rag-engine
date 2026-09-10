"""
Translation (R3)

Bidirectional Hungarian<->English translation for whichever language is
missing on a record. Goes through the LLM provider abstraction (R22) — never
calls an LLM API directly — and reads its system prompt from the PromptStore
(R24) so the translation instructions can be edited via the Admin UI without
redeploying.

Some providers/models wrap short translated phrases in markdown emphasis
(e.g. "**compressor**") despite being told not to — observed in practice
with Groq's gpt-oss-120b on single-word translations. Since translated text
here feeds directly into narrative prose (and from there into BM25 tokens
and embeddings), stray "**"/"*" characters would corrupt both. The prompt
asks for plain text, and the output is defensively stripped of markdown
emphasis as a safety net regardless of what any given provider actually does.

Usage:
    text_en = translate("Ipari szivattyuk gyartasa.", source_language="hu", target_language="en")
"""

import re

from loguru import logger

from bilingual_etl.providers.llm_provider import LLMProvider, generate_with_retry, get_llm_provider
from bilingual_etl.providers.prompt_store import PromptStore

LANGUAGE_NAMES = {"hu": "Hungarian", "en": "English"}

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_PATTERN = re.compile(r"\*(.+?)\*")


def _strip_markdown_emphasis(text: str) -> str:
    text = _BOLD_PATTERN.sub(r"\1", text)
    text = _ITALIC_PATTERN.sub(r"\1", text)
    return text


def other_language(language: str) -> str:
    if language not in LANGUAGE_NAMES:
        raise ValueError(f"Unsupported language '{language}'. Expected 'hu' or 'en'.")
    return "en" if language == "hu" else "hu"


def translate(
    text: str,
    source_language: str,
    target_language: str,
    llm: LLMProvider | None = None,
    prompt_store: PromptStore | None = None,
) -> str:
    if not text:
        return ""

    llm = llm or get_llm_provider()
    prompt_store = prompt_store or PromptStore()

    prompt = (
        f"Translate the following {LANGUAGE_NAMES[source_language]} text to "
        f"{LANGUAGE_NAMES[target_language]}:\n\n{text}"
    )
    system_prompt = prompt_store.get_translation_prompt()

    result = _strip_markdown_emphasis(generate_with_retry(llm, prompt, system_prompt=system_prompt))

    from bilingual_etl.providers.guardrails import validate_translation
    validate_translation(text, result, source_language, target_language)

    logger.info(
        f"Translated {source_language}->{target_language} "
        f"({len(text)} chars -> {len(result)} chars)"
    )
    return result
