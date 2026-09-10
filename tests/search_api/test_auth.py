"""Tests for POST /auth/login (R26)."""

from unittest.mock import patch

import bcrypt
from fastapi.testclient import TestClient

from search_api.main import app

client = TestClient(app)

TEST_HASH = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()


@patch("search_api.routers.auth.ADMIN_USERNAME", "testadmin")
@patch("search_api.routers.auth.ADMIN_PASSWORD_HASH", TEST_HASH)
def test_login_success():
    resp = client.post("/auth/login", json={"username": "testadmin", "password": "testpass"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 28800


@patch("search_api.routers.auth.ADMIN_USERNAME", "testadmin")
@patch("search_api.routers.auth.ADMIN_PASSWORD_HASH", TEST_HASH)
def test_login_wrong_password():
    resp = client.post("/auth/login", json={"username": "testadmin", "password": "wrong"})
    assert resp.status_code == 401


@patch("search_api.routers.auth.ADMIN_USERNAME", "testadmin")
@patch("search_api.routers.auth.ADMIN_PASSWORD_HASH", TEST_HASH)
def test_login_wrong_username():
    resp = client.post("/auth/login", json={"username": "hacker", "password": "testpass"})
    assert resp.status_code == 401


def test_admin_config_requires_auth():
    resp = client.get("/admin/config/")
    assert resp.status_code in (401, 403)


@patch("search_api.routers.auth.ADMIN_USERNAME", "testadmin")
@patch("search_api.routers.auth.ADMIN_PASSWORD_HASH", TEST_HASH)
def test_admin_config_accessible_with_jwt():
    login = client.post("/auth/login", json={"username": "testadmin", "password": "testpass"})
    token = login.json()["access_token"]
    resp = client.get("/admin/config/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
