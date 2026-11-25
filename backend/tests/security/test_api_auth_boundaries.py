"""Authentication bootstrap and privileged credential operations fail closed."""

import os
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from amberclaw.api.auth import create_access_token
from amberclaw.api.main import app
from amberclaw.security.tokens import RefreshTokenManager


def test_public_default_credentials_do_not_issue_tokens(monkeypatch):
    monkeypatch.delenv("AUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTH_CLIENT_SECRET", raising=False)
    result = TestClient(app).post(
        "/api/v1/auth/token",
        json={"client_id": "admin", "client_secret": "amberclaw-secret"},
    )
    assert result.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "access_token" not in result.json()


@pytest.mark.parametrize(
    "secret", [None, "short", "amberclaw-insecure-default-change-me-in-prod"]
)
def test_missing_or_unsafe_signing_key_cannot_issue_tokens(monkeypatch, secret):
    if secret is None:
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET_KEY", secret)
    with pytest.raises(HTTPException) as captured:
        create_access_token({"sub": "admin", "role": "admin"})
    assert captured.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/token/revoke", {"jti": "other-token"}),
        ("/api-keys", {"owner_id": "attacker", "scopes": ["*"]}),
        ("/api-keys/rotate", {"key_id": "other-key"}),
        ("/auth/break-glass", {"user_id": "attacker", "reason": "not authorized"}),
    ],
)
def test_credential_administration_requires_admin_identity(path, payload):
    client = TestClient(app)
    assert (
        client.post(f"/api/v1/auth{path}", json=payload).status_code
        == HTTPStatus.UNAUTHORIZED
    )
    token = create_access_token({"sub": "ordinary-user", "role": "user"})
    result = client.post(
        f"/api/v1/auth{path}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert result.status_code == HTTPStatus.FORBIDDEN


def test_refresh_token_cannot_authorize_api_requests():
    pair = RefreshTokenManager().create_token_pair("offline-admin", role="admin")
    client = TestClient(app)
    result = client.get(
        "/api/v1/agents", headers={"Authorization": f"Bearer {pair.refresh_token}"}
    )
    assert result.status_code == HTTPStatus.UNAUTHORIZED
    assert (
        client.get(
            "/api/v1/agents", headers={"Authorization": f"Bearer {pair.access_token}"}
        ).status_code
        == HTTPStatus.OK
    )


@pytest.mark.parametrize(
    "claims",
    [
        {"role": "admin", "sub": "attacker"},
        {"role": "admin", "exp": datetime.now(UTC) + timedelta(minutes=5)},
    ],
)
def test_tokens_require_identity_and_expiration(claims):
    token = jwt.encode(claims, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
    result = TestClient(app).get(
        "/api/v1/agents", headers={"Authorization": f"Bearer {token}"}
    )
    assert result.status_code == HTTPStatus.UNAUTHORIZED
