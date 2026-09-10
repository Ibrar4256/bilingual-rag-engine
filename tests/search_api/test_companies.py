"""Tests for POST /match/companies (R16) — Partner Boost, JSONB pre-filters."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from search_api.main import app
from search_api.routers.companies import PARTNER_BOOST

client = TestClient(app)


def _make_company_row(company_id, is_highlighted=False, lang="hu"):
    return {
        "company_id": company_id,
        "language": lang,
        "content_chunk": f"Chunk for {company_id}",
        "chunk_index": 0,
        "metadata": {"status": "OK"},
        "is_highlighted": is_highlighted,
        "rrf_score": 0.02,
        "embedding": [0.0] * 768,
    }


def test_partner_boost_value():
    assert PARTNER_BOOST == 1.15


def test_match_companies_rejects_empty_query():
    resp = client.post("/match/companies", json={"query": ""})
    assert resp.status_code == 422


@patch("search_api.routers.companies.get_connection")
@patch("search_api.routers.companies.get_embedding_provider")
@patch("search_api.routers.companies.detect_query_language", return_value="hu")
@patch("search_api.routers.companies.should_fallback", return_value=False)
def test_match_companies_response_shape(mock_fb, mock_lang, mock_emb, mock_conn):
    mock_provider = MagicMock()
    mock_provider.embed_single.return_value = [0.0] * 768
    mock_emb.return_value = mock_provider

    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.side_effect = [
        [{"company_id": "1", "language": "hu", "chunk_index": 0, "cosine_similarity": 0.9}],
        [{"company_id": "1", "language": "hu", "chunk_index": 0, "bm25_rank_score": 0.5}],
        [_make_company_row("1")],
    ]
    mock_connection = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    mock_conn.return_value = mock_connection

    resp = client.post("/match/companies", json={"query": "szivattyú"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["retrieval_mode"] == "hybrid_rrf"
    assert body["detected_language"] == "hu"
    assert isinstance(body["results"], list)


def test_single_company_rejects_empty_query():
    resp = client.post("/search/single-company", json={"company_id": "1", "query": ""})
    assert resp.status_code == 422
