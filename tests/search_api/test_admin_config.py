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
    put_resp = client.put(
        "/admin/config/test_setting",
        json={"value": {"enabled": True}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert put_resp.status_code == 200
    resp = client.get("/admin/config/test_setting", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "test_setting"
    assert body["value"]["enabled"] is True


def test_get_config_not_found():
    token = _get_token()
    resp = client.get("/admin/config/nonexistent_key", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_put_config_updates_value():
    token = _get_token()
    resp = client.put(
        "/admin/config/test_setting",
        json={"value": {"mode": "alpha"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["value"]["mode"] == "alpha"

    resp2 = client.put(
        "/admin/config/test_setting",
        json={"value": {"mode": "beta"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["value"]["mode"] == "beta"


def test_provider_availability_endpoint():
    token = _get_token()
    resp = client.get("/admin/config/providers/availability", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) > 0
