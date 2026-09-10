"""Tests for /admin/config/* (R24)."""

from unittest.mock import patch

import bcrypt
from fastapi.testclient import TestClient

from search_api.main import app

client = TestClient(app)

TEST_HASH = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()


def _get_token():
    with patch("search_api.routers.auth.ADMIN_USERNAME", "testadmin"), \
         patch("search_api.routers.auth.ADMIN_PASSWORD_HASH", TEST_HASH):
        resp = client.post("/auth/login", json={"username": "testadmin", "password": "testpass"})
        return resp.json()["access_token"]


def test_put_and_get_config_key():
    token = _get_token()
    client.put(
        "/admin/config/llm_provider",
        json={"value": {"active": "groq"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get("/admin/config/llm_provider", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "llm_provider"
    assert "active" in body["value"]


def test_get_config_not_found():
    token = _get_token()
    resp = client.get("/admin/config/nonexistent_key", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_put_config_updates_value():
    token = _get_token()
    resp = client.put(
        "/admin/config/llm_provider",
        json={"value": {"active": "gemini"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["value"]["active"] == "gemini"

    client.put(
        "/admin/config/llm_provider",
        json={"value": {"active": "groq"}},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_provider_availability_endpoint():
    token = _get_token()
    resp = client.get("/admin/config/providers/availability", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) > 0
