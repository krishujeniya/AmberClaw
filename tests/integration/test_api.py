"""Integration tests for API authentication, CORS, security headers, and routes."""

from fastapi.testclient import TestClient

from amberclaw.api.auth import create_access_token
from amberclaw.api.main import app

client = TestClient(app)


def test_health_endpoint_unauthenticated():
    """Health check endpoint should be accessible without authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_routes_require_auth():
    """Protected API routes must return 401 when no token is provided."""
    protected_endpoints = [
        ("GET", "/api/v1/tickets/pending"),
        ("POST", "/api/v1/agents/spawn"),
        ("POST", "/api/v1/a2a"),
    ]

    for method, endpoint in protected_endpoints:
        if method == "GET":
            response = client.get(endpoint)
        else:
            response = client.post(endpoint, json={})
        assert response.status_code == 401, (
            f"{endpoint} allowed unauthenticated access!"
        )


def test_protected_route_with_valid_jwt():
    """Protected API routes should allow access with a valid JWT token."""
    token = create_access_token(data={"sub": "test_user", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/tickets/pending", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_token_generation_endpoint():
    """Token endpoint should issue access token for valid credentials."""
    response = client.post(
        "/api/v1/auth/token",
        json={"client_id": "admin", "client_secret": "amberclaw-secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_security_headers_present():
    """HTTP responses must include standard security headers."""
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
