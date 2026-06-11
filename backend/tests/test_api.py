"""API smoke tests. Run against SQLite so CI needs no Postgres service."""

import os
import uuid

# Must be set before any app import — settings are read at import time.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-used"

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
