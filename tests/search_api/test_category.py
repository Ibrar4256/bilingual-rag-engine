"""Tests for POST /search/category (R15)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from search_api.main import app

client = TestClient(app)


def _mock_search_table(table, query, limit=20, offset=0, lang_override=None, extra_where="", extra_params=(), rerank=False):
    return {
        "detected_language": "hu",
        "response_time_ms": 42.0,
        "retrieval_mode": "hybrid_rrf",
        "cross_language_fallback_triggered": False,
        "results": [
            {
                "category_id": "904",
                "language": "hu",
                "narrative": "Test narrative",
                "metadata": {"ai_type": "category", "status": "OK"},
                "rrf_score": 0.033,
            }
        ],
    }


@patch("search_api.routers.category.search_table", side_effect=_mock_search_table)
def test_search_category_returns_r20_fields(mock_st):
    resp = client.post("/search/category", json={"query": "árnyékoló"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["detected_language"] == "hu"
    assert body["retrieval_mode"] == "hybrid_rrf"
    assert body["response_time_ms"] > 0
    assert isinstance(body["results"], list)
    assert body["results"][0]["category_id"] == "904"
    assert body["results"][0]["metadata"]["ai_type"] == "category"


@patch("search_api.routers.category.search_table", side_effect=_mock_search_table)
def test_search_category_forwards_language_override(mock_st):
    resp = client.post("/search/category", json={"query": "blinds", "language": "en"})
    assert resp.status_code == 200
    call_kwargs = mock_st.call_args
    assert call_kwargs.kwargs.get("lang_override") == "en" or call_kwargs[1].get("lang_override") == "en"


def test_search_category_rejects_empty_query():
    resp = client.post("/search/category", json={"query": ""})
    assert resp.status_code == 422
