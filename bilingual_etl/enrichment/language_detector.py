"""
Language detection for source records.

Uses the langdetect library (based on Google's language-detection algorithm)
to determine whether a text is Hungarian ('hu') or English ('en').

We need this because:
  - Source data is primarily Hungarian, but some records have English content
  - We need to know the source language to decide which direction to translate
  - The search API routes BM25 queries to language-specific columns
"""

from langdetect import detect, DetectorFactory
from loguru import logger

DetectorFactory.seed = 0


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "hu"

    try:
        detected = detect(text)
    except Exception:
        return "hu"

    if detected == "hu":
        return "hu"
    if detected in ("en", "en-US", "en-GB"):
        return "en"

    return "hu"


def detect_record_language(record: dict) -> str:
    text_parts = []

    for field in ("description", "short_description", "category_name", "company_name"):
        val = record.get(field)
        if val and isinstance(val, str) and val.strip():
            text_parts.append(val.strip())

    if not text_parts:
        activities = record.get("activities")
        if isinstance(activities, list):
            text_parts.extend(str(a) for a in activities[:5] if a)

    combined = " ".join(text_parts)
    lang = detect_language(combined)

    logger.debug(
        f"Detected language '{lang}' for record "
        f"{record.get('category_id') or record.get('company_id', '?')}"
    )
    return lang
