import pytest
from fastapi import status
from fastapi.testclient import TestClient
from amberclaw.api.main import app
from amberclaw.api.auth import create_access_token, API_KEY


@pytest.fixture
def client():
    return TestClient(app)


def test_unauthenticated_request_rejected(client):
    response = client.get("/api/v1/agents")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_invalid_bearer_token_rejected(client):
    response = client.get(
        "/api/v1/agents",
        headers={"Authorization": "Bearer invalid_garbage_token_12345"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_auth_token_generation_and_access(client):
    # Request access token
    token_resp = client.post(
        "/api/v1/auth/token",
        json={"client_id": "admin", "client_secret": "amberclaw-secret"},
    )
    assert token_resp.status_code == status.HTTP_200_OK
    data = token_resp.json()
    assert "access_token" in data

    token = data["access_token"]
    # Access protected route with valid token
    protected_resp = client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert protected_resp.status_code == status.HTTP_200_OK


def test_api_key_authentication(client, monkeypatch):
    test_key = "secret_api_key_12345"
    monkeypatch.setattr("amberclaw.api.auth.API_KEY", test_key)

    response = client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {test_key}"},
    )
    assert response.status_code == status.HTTP_200_OK
