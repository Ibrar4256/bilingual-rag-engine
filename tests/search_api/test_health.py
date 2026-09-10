from fastapi.testclient import TestClient

from search_api.main import app

client = TestClient(app)


def test_health_ok_against_real_db():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": True, "vector_index": True, "bm25_index": True}
    assert body["response_time_ms"] > 0


def test_health_degrades_when_db_unreachable(monkeypatch):
    def broken_connection():
        raise ConnectionError("simulated outage")

    monkeypatch.setattr("search_api.routers.health.get_connection", broken_connection)

    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"] == {"database": False, "vector_index": False, "bm25_index": False}
