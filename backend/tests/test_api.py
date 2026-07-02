"""API smoke tests. Run against SQLite so CI needs no Postgres service."""

import os
import uuid

# Must be set before any app import — settings are read at import time.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # tests hammer endpoints far past real limits

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _register_payload() -> dict:
    return {
        "email": f"test-{uuid.uuid4().hex[:10]}@example.com",
        "full_name": "Test User",
        "password": "supersecret123",
    }


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_register_login_me_flow() -> None:
    payload = _register_payload()
    with TestClient(app) as client:
        # Register
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == payload["email"]
        assert "access_token" in body

        # Duplicate registration is rejected
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 409

        # Login
        response = client.post(
            "/api/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Authenticated /me
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == payload["email"]

        # Wrong password is rejected
        response = client.post(
            "/api/auth/login", json={"email": payload["email"], "password": "wrong-password"}
        )
        assert response.status_code == 401


def test_protected_routes_require_auth() -> None:
    with TestClient(app) as client:
        assert client.get("/api/documents").status_code == 401
        assert client.get("/api/conversations").status_code == 401
        assert client.get("/api/analytics/overview").status_code == 401


def test_password_longer_than_bcrypt_limit_rejected() -> None:
    # bcrypt only reads 72 bytes; the API must reject anything longer instead
    # of silently ignoring the tail of the password.
    payload = _register_payload() | {"password": "x" * 73}
    with TestClient(app) as client:
        assert client.post("/api/auth/register", json=payload).status_code == 422


def test_refresh_token_flow() -> None:
    payload = _register_payload()
    with TestClient(app) as client:
        body = client.post("/api/auth/register", json=payload).json()
        refresh = body["refresh_token"]

        # Refresh returns a new pair and rotates the old token out.
        response = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert response.status_code == 200
        new_pair = response.json()
        assert new_pair["access_token"] != body["access_token"]

        # New access token works.
        response = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {new_pair['access_token']}"}
        )
        assert response.status_code == 200

        # The rotated (already-used) refresh token is rejected...
        response = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert response.status_code == 401

        # ...and reuse triggers revocation of the whole session family.
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": new_pair["refresh_token"]}
        )
        assert response.status_code == 401


def test_logout_revokes_refresh_token() -> None:
    payload = _register_payload()
    with TestClient(app) as client:
        body = client.post("/api/auth/register", json=payload).json()
        refresh = body["refresh_token"]

        assert client.post("/api/auth/logout", json={"refresh_token": refresh}).status_code == 204
        assert client.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    payload = _register_payload()
    with TestClient(app) as client:
        refresh = client.post("/api/auth/register", json=payload).json()["refresh_token"]
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh}"})
        assert response.status_code == 401


def test_analytics_overview_empty_account() -> None:
    payload = _register_payload()
    with TestClient(app) as client:
        token = client.post("/api/auth/register", json=payload).json()["access_token"]
        response = client.get(
            "/api/analytics/overview", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_documents"] == 0
        assert body["questions_asked"] == 0
