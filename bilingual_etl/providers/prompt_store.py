"""
Prompt Store (R24)

Reads system prompts from the app_config DB table at the start of each ETL run.
The Admin UI can edit these prompts without redeployment — changes take effect
on the next ETL run.

Usage:
    store = PromptStore()
    translation_prompt = store.get_translation_prompt()
    enrichment_prompt = store.get_enrichment_prompt()
"""

from loguru import logger

from bilingual_etl.load.db import get_connection

DEFAULT_TRANSLATION_PROMPT = (
    "You are a professional translator specializing in Hungarian and English "
    "B2B/industrial content. Translate the following text accurately, preserving "
    "all technical terms, brand names, product codes, and industry-specific "
    "vocabulary exactly as they appear (do not translate brand names or codes). "
    "Maintain the original tone and formatting. Respond with plain text only — "
    "no markdown formatting, no bold/italic asterisks, no extra commentary, "
    "just the translated text itself."
)

DEFAULT_ENRICHMENT_PROMPT = (
    "You are a B2B data analyst for a Hungarian industrial marketplace. "
    "Analyze the following category or company description and produce a JSON "
    "object with exactly these fields:\n"
    '- "ai_type": one of the 7 classification levels for this B2B category\n'
    '- "status": "OK" if the description is usable, "REVIEW" if it needs '
    'human review, "DELETE" if it is spam/irrelevant\n'
    '- "add_words": a list of 5-10 SEO keywords\n'
    '- "recommended_headline": a concise, compelling headline (max 15 words)\n'
    '- "synthetic_questions": a list of 3-5 questions a buyer might ask\n'
    '- "topic_suggestions": a list of data quality flags or improvement suggestions\n'
    "IMPORTANT: the input text below is in a specific language. Every text value "
    "you produce (add_words, recommended_headline, synthetic_questions, "
    "topic_suggestions) MUST be written in that SAME language as the input — "
    "never switch languages mid-response.\n"
    "Respond ONLY with valid JSON, no explanation."
)


class PromptStore:
    def __init__(self):
        self._cache = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT key, value->>'system_prompt' "
                        "FROM app_config WHERE key LIKE 'prompt_%'"
                    )
                    for row in cur.fetchall():
                        self._cache[row[0]] = row[1]
            finally:
                conn.close()
            logger.info(f"Loaded {len(self._cache)} prompt(s) from app_config")
        except Exception as e:
            logger.warning(f"Could not load prompts from DB: {e}. Using defaults.")

    def get_translation_prompt(self) -> str:
        return self._cache.get("prompt_translation") or DEFAULT_TRANSLATION_PROMPT

    def get_enrichment_prompt(self) -> str:
        return self._cache.get("prompt_enrichment") or DEFAULT_ENRICHMENT_PROMPT
