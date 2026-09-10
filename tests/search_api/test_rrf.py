from search_api.services.rrf import DEFAULT_K, SECONDARY_LANGUAGE_WEIGHT, fuse_rankings


def test_item_ranked_first_in_all_sources_wins():
    fused = fuse_rankings(
        vector_results=["a", "b", "c"],
        bm25_primary_results=["a", "c", "b"],
    )
    assert fused[0][0] == "a"


def test_score_matches_rrf_formula():
    fused = dict(fuse_rankings(vector_results=["a", "b"], bm25_primary_results=["b", "a"]))
    k = DEFAULT_K
    assert fused["a"] == 1 / (k + 1) + 1 / (k + 2)
    assert fused["b"] == 1 / (k + 2) + 1 / (k + 1)


def test_secondary_language_bm25_is_downweighted():
    fused = dict(
        fuse_rankings(
            vector_results=[],
            bm25_primary_results=[],
            bm25_secondary_results=["a"],
        )
    )
    k = DEFAULT_K
    assert fused["a"] == SECONDARY_LANGUAGE_WEIGHT / (k + 1)


def test_item_missing_from_a_source_gets_no_contribution_from_it():
    fused = dict(fuse_rankings(vector_results=["a"], bm25_primary_results=["b"]))
    k = DEFAULT_K
    assert fused["a"] == 1 / (k + 1)
    assert fused["b"] == 1 / (k + 1)
    assert "c" not in fused


def test_never_a_weighted_average_of_raw_scores():
    # Regression guard for the explicit CLAUDE.md constraint: fusion must be
    # rank-based RRF, not `weight * raw_score` blending. A pure vector match
    # ranked #1 must always outscore a BM25-only match ranked #1, by exactly
    # the RRF formula — not by whatever raw similarity/ts_rank happened to be.
    fused = dict(fuse_rankings(vector_results=["a"], bm25_primary_results=["b"]))
    assert fused["a"] == fused["b"]


def test_results_sorted_descending_by_score():
    fused = fuse_rankings(
        vector_results=["a", "b", "c"],
        bm25_primary_results=["a", "b", "c"],
    )
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)
