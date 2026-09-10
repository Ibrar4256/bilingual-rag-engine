"""
Reciprocal Rank Fusion (R13, R14)

RRF combines multiple ranked result lists using only each item's *rank*
(1st, 2nd, 3rd...) in each list, never the raw similarity/relevance scores.
That's what makes it safe to combine vector cosine-similarity with BM25
ts_rank: the two scores live on incomparable scales, so blending them
directly (e.g. 0.7*vector + 0.3*bm25) would silently let whichever source
happens to produce larger numbers dominate. CLAUDE.md forbids that weighted-
average approach explicitly — RRF sidesteps the problem instead of tuning
around it.

score(item) = sum over sources of weight_source / (k + rank_in_source)

k=60 is the RRF default from the original paper (Cormack et al., 2009) —
large enough that a #1 vs #2 rank difference doesn't overwhelm an item that
scores well across multiple sources.

R14's bilingual weighting: vector search has no language column (embeddings
are language-agnostic), so it always gets full weight. BM25 is language-
specific — the detected/requested language's BM25 column gets full weight,
and the other language's BM25 column (used for cross-language recall) is
downweighted to 0.5 so it can surface a good secondary-language match
without letting it outrank a same-language one.
"""

from loguru import logger

DEFAULT_K = 60
SECONDARY_LANGUAGE_WEIGHT = 0.5


def fuse_rankings(
    vector_results: list[str],
    bm25_primary_results: list[str],
    bm25_secondary_results: list[str] | None = None,
    k: int = DEFAULT_K,
) -> list[tuple[str, float]]:
    """
    Fuse ranked ID lists into a single RRF-scored, descending-sorted list.

    Each input is a list of item IDs already ordered best-first by its own
    source (vector similarity DESC, or BM25 ts_rank DESC). An item missing
    from a source contributes nothing from that source — it is not treated
    as ranked last, since RRF's rank-based formula requires an actual rank.
    """
    bm25_secondary_results = bm25_secondary_results or []
    scores: dict[str, float] = {}

    for rank, item_id in enumerate(vector_results, start=1):
        scores[item_id] = scores.get(item_id, 0.0) + 1 / (k + rank)

    for rank, item_id in enumerate(bm25_primary_results, start=1):
        scores[item_id] = scores.get(item_id, 0.0) + 1 / (k + rank)

    for rank, item_id in enumerate(bm25_secondary_results, start=1):
        scores[item_id] = scores.get(item_id, 0.0) + SECONDARY_LANGUAGE_WEIGHT / (k + rank)

    fused = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)

    logger.info(
        "EVIDENCE_API_RRF_MERGE: "
        f"vector_candidates={len(vector_results)} "
        f"bm25_primary_candidates={len(bm25_primary_results)} "
        f"bm25_secondary_candidates={len(bm25_secondary_results)} "
        f"fused_candidates={len(fused)} k={k}"
    )

    return fused
