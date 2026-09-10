"""
Company Chunker (R7)

Splits a company's narrative into chunks of at most 500 words each, so
that embeddings and BM25 tokens stay meaningful for a single search
result (a 5,000-word narrative embedded as one vector would blur every
topic in it together). Splitting happens on sentence boundaries where
possible, so a chunk never cuts a sentence in half.

Each chunk is prefixed with a short bilingual context header — "bilingual"
in the sense that both a Hungarian and an English tag pair exist
([CÉG:]/[PROFIL:] vs [COMPANY:]/[PROFILE:]); a single chunk uses whichever
pair matches its own row's language, since company_vectors stores one row
per (company_id, language, chunk_index) — never both languages in one row.
The header's word count is not counted against the 500-word body limit;
it is a small, fixed-size piece of retrieval context, not searchable prose.

Per R7, synthetic buyer questions (from bilingual_etl/enrichment/ai_enrichment.py)
are appended to the narrative BEFORE chunking, so they become searchable
content woven into whichever chunk they land in, rather than living in a
separate field that search never looks at.

Usage:
    narrative = append_synthetic_questions(narrative, questions, language="en")
    chunks = chunk_company_narrative(narrative, company_name, profile_line, language="en")
"""

import re

MAX_WORDS_PER_CHUNK = 500

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_PATTERN.split(text.strip()) if s.strip()]


def _build_header(company_name: str, profile_line: str, language: str) -> str:
    if language == "hu":
        return f"[CÉG:] {company_name}\n[PROFIL:] {profile_line}"
    return f"[COMPANY:] {company_name}\n[PROFILE:] {profile_line}"


def append_synthetic_questions(narrative: str, questions: list[str], language: str) -> str:
    if not questions:
        return narrative

    heading = "Gyakran ismételt kérdések:" if language == "hu" else "Frequently asked questions:"
    questions_block = " ".join(questions)
    return f"{narrative} {heading} {questions_block}"


def chunk_text(text: str, max_words: int = MAX_WORDS_PER_CHUNK) -> list[str]:
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)
    chunks: list[str] = []
    current_words: list[str] = []

    for sentence in sentences:
        sentence_words = sentence.split()

        if current_words and len(current_words) + len(sentence_words) > max_words:
            chunks.append(" ".join(current_words))
            current_words = []

        current_words.extend(sentence_words)

        # A single sentence longer than the limit (e.g. a giant comma-separated
        # category list with no internal punctuation) must still be split.
        while len(current_words) > max_words:
            chunks.append(" ".join(current_words[:max_words]))
            current_words = current_words[max_words:]

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def chunk_company_narrative(
    narrative: str,
    company_name: str,
    profile_line: str,
    language: str,
    max_words: int = MAX_WORDS_PER_CHUNK,
) -> list[str]:
    header = _build_header(company_name, profile_line, language)
    body_chunks = chunk_text(narrative, max_words=max_words)
    return [f"{header}\n\n{chunk}" for chunk in body_chunks]
