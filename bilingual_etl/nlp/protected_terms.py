"""
Protected Terms Masking (R8)

Brand names, product codes, and certificate codes (e.g. "Bunting", "ISO 9001")
must survive lemmatization unchanged. Lemmatizers reduce words to their base
form ("Bunting" -> "bunt"), which destroys brand names.

The fix: mask every protected term with a placeholder BEFORE lemmatization,
then unmask (restore the original text) AFTER. This ordering is a correctness
requirement (AC-2), not a style choice — reversing it corrupts protected terms.

Usage:
    masker = ProtectedTermsMasker()
    masked_text, mapping = masker.mask("We use Bunting magnets, ISO 9001 certified.")
    # masked_text: "We use zzzptermzzz0zzz magnets, zzzptermzzz1zzz certified."
    # ... run lemmatization on masked_text here ...
    original = masker.unmask(masked_text, mapping)
    # original: "We use Bunting magnets, ISO 9001 certified."
"""

import json
import re
from pathlib import Path

DEFAULT_WHITELIST_PATH = Path(__file__).parent / "whitelists" / "brands_whitelist.json"
PLACEHOLDER_TEMPLATE = "zzzptermzzz{index}zzz"
PLACEHOLDER_PATTERN = re.compile(r"zzzptermzzz(\d+)zzz", re.IGNORECASE)


def load_whitelist(path: Path = DEFAULT_WHITELIST_PATH) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_pattern(terms: list[str]) -> re.Pattern:
    # Longest terms first so "ABS MF" matches before "ABS" at the same position.
    sorted_terms = sorted(terms, key=len, reverse=True)
    alternation = "|".join(re.escape(t) for t in sorted_terms)
    return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)", re.IGNORECASE)


class ProtectedTermsMasker:
    def __init__(self, whitelist_path: Path = DEFAULT_WHITELIST_PATH):
        self._terms = load_whitelist(whitelist_path)
        self._pattern = _build_pattern(self._terms)

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        if not text:
            return text, {}

        mapping: dict[str, str] = {}
        counter = 0

        def _replace(match: re.Match) -> str:
            nonlocal counter
            placeholder = PLACEHOLDER_TEMPLATE.format(index=counter)
            mapping[placeholder] = match.group(0)
            counter += 1
            return placeholder

        masked_text = self._pattern.sub(_replace, text)
        return masked_text, mapping

    def unmask(self, text: str, mapping: dict[str, str]) -> str:
        if not mapping:
            return text

        def _restore(match: re.Match) -> str:
            placeholder = match.group(0).lower()
            return mapping.get(placeholder, match.group(0))

        return PLACEHOLDER_PATTERN.sub(_restore, text)
