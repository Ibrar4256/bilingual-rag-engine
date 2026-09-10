"""Tests for company chunking (R7)."""

from bilingual_etl.transform.chunker import (
    MAX_WORDS_PER_CHUNK,
    append_synthetic_questions,
    chunk_company_narrative,
    chunk_text,
)


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("A short sentence. Another short sentence.")
        assert len(chunks) == 1

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_respects_max_words_limit(self):
        # 3 sentences of 200 words each = 600 words total, must split into 2+ chunks
        sentence = " ".join(["word"] * 200) + "."
        text = " ".join([sentence] * 3)

        chunks = chunk_text(text, max_words=500)

        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk.split()) <= 500

    def test_does_not_split_mid_sentence_when_avoidable(self):
        sentence_a = "Alpha " * 100 + "."
        sentence_b = "Beta " * 100 + "."
        sentence_c = "Gamma " * 100 + "."
        text = f"{sentence_a} {sentence_b} {sentence_c}"

        chunks = chunk_text(text, max_words=150)

        # Each sentence is a single repeated word — verify no chunk contains
        # a mix of two different repeated words (which would mean a sentence
        # got split, since 100 < 150 the limit).
        for chunk in chunks:
            words_present = {w for w in chunk.split() if w != "."}
            assert len(words_present) <= 1

    def test_single_sentence_longer_than_limit_gets_hard_split(self):
        # A single giant comma-separated "sentence" with no internal periods —
        # exactly the shape of a 600+ category list rendered as one sentence.
        text = ", ".join([f"item{i}" for i in range(700)]) + "."

        chunks = chunk_text(text, max_words=500)

        assert len(chunks) == 2
        assert len(chunks[0].split()) == 500

    def test_default_max_words_constant(self):
        assert MAX_WORDS_PER_CHUNK == 500


class TestAppendSyntheticQuestions:
    def test_appends_questions_hu(self):
        result = append_synthetic_questions("Narrative text.", ["Kérdés egy?", "Kérdés kettő?"], "hu")
        assert "Narrative text." in result
        assert "Kérdés egy?" in result
        assert "Gyakran ismételt kérdések" in result

    def test_appends_questions_en(self):
        result = append_synthetic_questions("Narrative text.", ["Question one?"], "en")
        assert "Frequently asked questions" in result
        assert "Question one?" in result

    def test_no_questions_returns_narrative_unchanged(self):
        result = append_synthetic_questions("Narrative text.", [], "en")
        assert result == "Narrative text."


class TestChunkCompanyNarrative:
    def test_every_chunk_has_header(self):
        narrative = "Sentence one. Sentence two. Sentence three."
        chunks = chunk_company_narrative(narrative, "Test Kft.", "pumps and parts", "hu")

        for chunk in chunks:
            assert "[CÉG:] Test Kft." in chunk
            assert "[PROFIL:] pumps and parts" in chunk

    def test_english_header_tags(self):
        narrative = "Sentence one."
        chunks = chunk_company_narrative(narrative, "Test Kft.", "pumps and parts", "en")

        assert "[COMPANY:] Test Kft." in chunks[0]
        assert "[PROFILE:] pumps and parts" in chunks[0]
        assert "[CÉG:]" not in chunks[0]

    def test_large_narrative_produces_multiple_headed_chunks(self):
        long_list = ", ".join([f"Category{i}" for i in range(700)]) + "."
        narrative = f"Intro sentence. {long_list}"

        chunks = chunk_company_narrative(narrative, "Big Kft.", "many categories", "hu")

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.startswith("[CÉG:] Big Kft.")

    def test_empty_narrative_produces_no_chunks(self):
        chunks = chunk_company_narrative("", "Test Kft.", "profile", "hu")
        assert chunks == []
