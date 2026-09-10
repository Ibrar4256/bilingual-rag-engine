---
paths: bilingual_etl/nlp/**, bilingual_etl/enrichment/**, search_api/services/**
---

# Bilingual NLP Rules

- Protected Terms masking always runs before lemmatization and unmasking always runs after — reordering this corrupts brand names/codes (e.g. "Bunting" → "bunt"). This is the #1 UAT acceptance criterion (AC-2); treat it as non-negotiable.
- Hungarian text uses `huspacy` (`hu_core_news_lg`); English text uses `spaCy` (`en_core_web_lg`) — never cross-apply a model to the wrong language's text.
- The embedding path always uses the raw (non-lemmatized) narrative — lemmatization is BM25-only. Embedding inflected Hungarian forms (e.g. "kínálunk" vs "kínál") preserves semantic nuance that lemmatization would flatten.
- Every category/company gets a row in both languages (R3, R6) — if a translation call fails, that's a pipeline error to surface, not a reason to write a single-language row.
- The `ai_type` taxonomy has only 1 of 7 levels documented by the client (`GÉP_ÉS_BERENDEZÉS`) — treat any other level name as a placeholder/assumption and flag it in the traceability table rather than presenting it as client-confirmed.
