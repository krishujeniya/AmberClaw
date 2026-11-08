"""Integration tests for Enterprise SSO API routes."""

import base64
import re
import zlib
from http import HTTPStatus
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from amberclaw.api.main import app
from amberclaw.api.v1.sso_router import set_sso_config
from amberclaw.security.sso.models import SSOConfig
from tests.sso_helpers import SigningIdentity


@pytest.fixture(autouse=True)
def configured_sso():
    identity = SigningIdentity()
    config = SSOConfig(enabled=True, idp_x509_cert=identity.cert)
    set_sso_config(config)
    yield identity, config
    set_sso_config(SSOConfig())


def test_sso_metadata_endpoint() -> None:
    """Test GET /api/v1/auth/sso/metadata returns valid XML metadata."""
    client = TestClient(app)
    response = client.get("/api/v1/auth/sso/metadata")
    assert response.status_code == 200  # noqa: PLR2004
    assert "application/xml" in response.headers["content-type"]
    assert "<md:EntityDescriptor" in response.text


def test_sso_login_endpoint() -> None:
    """Test GET /api/v1/auth/sso/login returns redirect to IdP."""
    client = TestClient(app, follow_redirects=False)
    response = client.get("/api/v1/auth/sso/login?relay_state=%2Fdashboard")
    assert response.status_code in (302, 307)
    assert (
        "https://idp.enterprise.com/saml/sso?SAMLRequest="
        in response.headers["location"]
    )


def test_sso_callback_rejects_unsigned_unsolicited_saml() -> None:
    """An unsigned assertion supplied by a caller must never issue a JWT."""

    saml_xml = """<?xml version="1.0"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" Version="2.0">
    <samlp:Status>
        <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
    </samlp:Status>
    <saml:Assertion Version="2.0">
        <saml:Subject>
            <saml:NameID>saml.user@corp.com</saml:NameID>
        </saml:Subject>
        <saml:AttributeStatement>
            <saml:Attribute Name="displayName"><saml:AttributeValue>SAML Corp User</saml:AttributeValue></saml:Attribute>
            <saml:Attribute Name="roles"><saml:AttributeValue>AmberClaw-Admins</saml:AttributeValue></saml:Attribute>
        </saml:AttributeStatement>
    </saml:Assertion>
</samlp:Response>"""

    b64_response = base64.b64encode(saml_xml.encode("utf-8")).decode("utf-8")

    client = TestClient(app)
    res = client.post("/api/v1/auth/sso/callback", json={"SAMLResponse": b64_response})
    assert res.status_code == HTTPStatus.UNAUTHORIZED
    assert "access_token" not in res.json()


def test_sso_callback_rejects_raw_oidc_claims() -> None:
    """Caller-supplied identity claims are not an identity credential."""
    client = TestClient(app)
    claims_payload = {
        "claims": {
            "email": "oidc.user@corp.com",
            "name": "OIDC User",
            "roles": ["operator"],
            "sub": "oidc-sub-12345",
        }
    }
    res = client.post("/api/v1/auth/sso/callback", json=claims_payload)
    assert res.status_code == HTTPStatus.UNAUTHORIZED
    assert "access_token" not in res.json()


def test_sso_callback_empty_payload() -> None:
    """Test POST /api/v1/auth/sso/callback with missing payload returns 400."""
    client = TestClient(app)
    res = client.post("/api/v1/auth/sso/callback", json={})
    assert res.status_code == 400  # noqa: PLR2004
    assert "Missing SAMLResponse or authorization code" in res.text


def test_sso_signed_saml_login_is_browser_bound_and_single_use(configured_sso):
    identity, config = configured_sso
    client = TestClient(app, base_url="https://amberclaw.ai", follow_redirects=False)
    login = client.get("/api/v1/auth/sso/login")
    assert login.status_code == HTTPStatus.FOUND
    assert "Secure" in login.headers["set-cookie"]
    query = parse_qs(urlsplit(login.headers["location"]).query)
    xml = zlib.decompress(base64.b64decode(query["SAMLRequest"][0]), -15).decode()
    request_id = re.search(r'\bID="([^"]+)"', xml).group(1)
    payload = {
        "SAMLResponse": identity.saml_response(config, request_id),
        "RelayState": query["RelayState"][0],
    }
    stranger = TestClient(app, base_url="https://amberclaw.ai")
    assert (
        stranger.post("/api/v1/auth/sso/callback", data=payload).status_code
        == HTTPStatus.UNAUTHORIZED
    )
    result = client.post("/api/v1/auth/sso/callback", data=payload)
    assert result.status_code == HTTPStatus.OK, result.text
    assert result.json()["user_profile"]["roles"] == ["admin"]
    assert "access_token" in result.json()
    assert (
        client.post("/api/v1/auth/sso/callback", data=payload).status_code
        == HTTPStatus.UNAUTHORIZED
    )


def test_sso_disabled_never_issues_tokens():
    set_sso_config(SSOConfig())
    client = TestClient(app)
    for path in ("metadata", "login"):
        assert (
            client.get(f"/api/v1/auth/sso/{path}").status_code == HTTPStatus.NOT_FOUND
        )
    assert (
        client.post(
            "/api/v1/auth/sso/callback", json={"claims": {"sub": "admin"}}
        ).status_code
        == HTTPStatus.NOT_FOUND
    )
