"""Real signed OIDC tokens over mocked discovery, token and JWKS endpoints."""

import base64
import hashlib
import json
import time
from functools import partial
from http import HTTPStatus
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from jwt.algorithms import RSAAlgorithm
from starlette.testclient import TestClient

from amberclaw.api.main import app
from amberclaw.api.v1.sso_router import set_sso_config
from amberclaw.security.sso import oidc
from amberclaw.security.sso.models import SSOConfig, SSOProtocol
from tests.sso_helpers import SigningIdentity


@pytest.mark.parametrize(
    "invalid", [None, "signature", "issuer", "audience", "nonce", "expired", "unsigned"]
)
def test_oidc_callback_verifies_token_and_consumes_request(monkeypatch, invalid):
    identity = SigningIdentity()
    config = SSOConfig(
        enabled=True,
        protocol=SSOProtocol.OIDC,
        oidc_issuer_url="https://idp.example",
        oidc_client_id="offline-client",
    )
    set_sso_config(config)
    login_params = {}
    public_key = {
        **json.loads(RSAAlgorithm.to_jwk(load_pem_public_key(identity.public))),
        "kid": "offline",
    }

    def provider(request):
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(
                HTTPStatus.OK,
                json={
                    "issuer": config.oidc_issuer_url,
                    "authorization_endpoint": "https://idp.example/authorize",
                    "token_endpoint": "https://idp.example/token",
                    "jwks_uri": "https://idp.example/keys",
                },
            )
        if request.url.path == "/keys":
            return httpx.Response(HTTPStatus.OK, json={"keys": [public_key]})
        assert request.url.path == "/token"
        assert request.method == "POST"
        fields = parse_qs(request.content.decode())
        assert fields["code"] == ["single-use-code"]
        assert fields["redirect_uri"] == [config.sp_acs_url]
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(fields["code_verifier"][0].encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        assert [challenge] == login_params["code_challenge"]
        claims = {
            "iss": config.oidc_issuer_url,
            "sub": "offline-user",
            "aud": config.oidc_client_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "nonce": login_params["nonce"][0],
            "email": "verified@example.com",
            "roles": ["operator"],
        }
        if invalid in {"issuer", "audience", "nonce"}:
            claims[{"issuer": "iss", "audience": "aud", "nonce": "nonce"}[invalid]] = (
                "wrong"
            )
        if invalid == "expired":
            claims["exp"] = int(time.time()) - 600
        signing_key = SigningIdentity().key if invalid == "signature" else identity.key
        token = jwt.encode(
            claims, signing_key, algorithm="RS256", headers={"kid": "offline"}
        )
        if invalid == "unsigned":
            header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
            token = f"{header}.{token.split('.')[1]}."
        return httpx.Response(
            HTTPStatus.OK,
            json={
                "id_token": token,
                "access_token": "offline-token",
                "token_type": "Bearer",
            },
        )

    transport = httpx.MockTransport(provider)
    monkeypatch.setattr(
        oidc, "AsyncOAuth2Client", partial(oidc.AsyncOAuth2Client, transport=transport)
    )
    monkeypatch.setattr(
        oidc,
        "httpx",
        SimpleNamespace(AsyncClient=partial(httpx.AsyncClient, transport=transport)),
    )
    try:
        client = TestClient(
            app, base_url="https://amberclaw.ai", follow_redirects=False
        )
        login = client.get("/api/v1/auth/sso/login")
        assert login.status_code == HTTPStatus.FOUND, login.text
        login_params.update(parse_qs(urlsplit(login.headers["location"]).query))
        assert login_params["code_challenge_method"] == ["S256"]
        params = {"code": "single-use-code", "state": login_params["state"][0]}
        stranger = TestClient(app, base_url="https://amberclaw.ai")
        assert (
            stranger.get("/api/v1/auth/sso/callback", params=params).status_code
            == HTTPStatus.UNAUTHORIZED
        )
        result = client.get("/api/v1/auth/sso/callback", params=params)
        expected = HTTPStatus.UNAUTHORIZED if invalid else HTTPStatus.OK
        assert result.status_code == expected, result.text
        if not invalid:
            assert result.json()["user_profile"]["email"] == "verified@example.com"
        else:
            assert "access_token" not in result.json()
        assert (
            client.get("/api/v1/auth/sso/callback", params=params).status_code
            == HTTPStatus.UNAUTHORIZED
        )
    finally:
        set_sso_config(SSOConfig())
