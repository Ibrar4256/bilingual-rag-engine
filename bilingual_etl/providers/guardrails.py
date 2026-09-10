"""
LLM Output Guardrails — validate and retry malformed LLM responses.

Provides:
  - JSON schema validation with automatic retry + corrective feedback
  - Content safety checks (empty, too short, suspicious patterns)
  - RAG answer validation (citation presence, hallucination markers)

Every validation failure is logged with EVIDENCE_GUARDRAIL_* markers.
"""

import json
import re

from loguru import logger

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

MAX_GUARDRAIL_RETRIES = 2


def strip_code_fences(raw: str) -> str:
    return _CODE_FENCE_PATTERN.sub("", raw).strip()


def validate_json_response(
    raw: str,
    required_fields: list[str],
    field_types: dict[str, type] | None = None,
) -> tuple[dict | None, list[str]]:
    """Parse and validate a JSON response from an LLM.

    Returns (parsed_dict, errors). If errors is non-empty, parsed_dict may be None.
    """
    errors = []
    cleaned = strip_code_fences(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return None, errors

    if not isinstance(data, dict):
        errors.append(f"Expected JSON object, got {type(data).__name__}")
        return None, errors

    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if field_types:
        for field, expected_type in field_types.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    errors.append(
                        f"Field '{field}' should be {expected_type.__name__}, "
                        f"got {type(data[field]).__name__}"
                    )

    return data, errors


def generate_with_guardrails(
    llm,
    prompt: str,
    system_prompt: str,
    required_fields: list[str],
    field_types: dict[str, type] | None = None,
    max_retries: int = MAX_GUARDRAIL_RETRIES,
) -> tuple[dict | None, list[str]]:
    """Generate LLM output and validate it as JSON with required fields.

    On validation failure, retries with corrective feedback appended to the prompt.
    Returns (parsed_data, all_errors_from_last_attempt).
    """
    from bilingual_etl.providers.llm_provider import generate_with_retry

    current_prompt = prompt
    all_errors = []

    for attempt in range(1, max_retries + 2):
        raw = generate_with_retry(llm, current_prompt, system_prompt=system_prompt)
        data, errors = validate_json_response(raw, required_fields, field_types)

        if not errors and data is not None:
            if attempt > 1:
                logger.info(
                    f"EVIDENCE_GUARDRAIL_RETRY_SUCCESS: "
                    f"succeeded on attempt {attempt} after {len(all_errors)} prior errors"
                )
            return data, []

        all_errors.extend(errors)
        logger.warning(
            f"EVIDENCE_GUARDRAIL_VALIDATION_FAIL: attempt {attempt}/{max_retries + 1} "
            f"errors={errors}"
        )

        if attempt <= max_retries:
            feedback = (
                f"\n\nYour previous response had validation errors:\n"
                + "\n".join(f"- {e}" for e in errors)
                + "\n\nPlease fix these issues and respond with valid JSON containing "
                f"all required fields: {', '.join(required_fields)}"
            )
            current_prompt = prompt + feedback

    logger.error(
        f"EVIDENCE_GUARDRAIL_EXHAUSTED: all {max_retries + 1} attempts failed. "
        f"Errors: {all_errors}"
    )
    return data, all_errors


def validate_rag_answer(answer: str, citations: list[dict]) -> list[str]:
    """Validate a RAG-generated answer for quality issues."""
    warnings = []

    if not answer or len(answer.strip()) < 10:
        warnings.append("Answer is empty or too short")

    if citations and not re.search(r"\[\d+\]", answer):
        warnings.append("Answer has context documents but no citation references [N]")

    hallucination_markers = [
        "I don't have access to",
        "I cannot access",
        "As an AI language model",
        "I'm not able to browse",
        "my training data",
    ]
    for marker in hallucination_markers:
        if marker.lower() in answer.lower():
            warnings.append(f"Possible hallucination marker: '{marker}'")
            break

    if len(answer) > 5000:
        warnings.append(f"Answer unusually long ({len(answer)} chars)")

    if warnings:
        logger.warning(f"EVIDENCE_GUARDRAIL_RAG_WARNINGS: {warnings}")

    return warnings


def validate_translation(original: str, translated: str, source_lang: str, target_lang: str) -> list[str]:
    """Basic translation quality checks."""
    warnings = []

    if not translated or not translated.strip():
        warnings.append("Translation is empty")

    if translated.strip() == original.strip():
        warnings.append("Translation is identical to original — may not have been translated")

    if len(original) > 10 and len(translated) < len(original) * 0.2:
        warnings.append(
            f"Translation suspiciously short ({len(translated)} chars vs "
            f"{len(original)} chars original)"
        )

    if len(translated) > len(original) * 5:
        warnings.append(
            f"Translation suspiciously long ({len(translated)} chars vs "
            f"{len(original)} chars original)"
        )

    if warnings:
        logger.warning(
            f"EVIDENCE_GUARDRAIL_TRANSLATION_WARNINGS: {source_lang}->{target_lang} {warnings}"
        )

    return warnings
