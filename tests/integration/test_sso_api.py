"""Integration tests for Enterprise SSO API routes."""

import base64

from starlette.testclient import TestClient

from amberclaw.api.main import app
from amberclaw.api.v1.sso_router import set_sso_config
from amberclaw.security.sso.models import SSOConfig


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
    assert "https://idp.enterprise.com/saml/sso?SAMLRequest=" in response.headers["location"]


def test_sso_callback_saml_success() -> None:
    """Test POST /api/v1/auth/sso/callback with valid SAML assertion issues JWT."""
    config = SSOConfig(role_mapping={"AmberClaw-Admins": "admin"})
    set_sso_config(config)

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
    assert res.status_code == 200  # noqa: PLR2004
    data = res.json()
    assert "access_token" in data
    assert data["user_profile"]["email"] == "saml.user@corp.com"
    assert "admin" in data["user_profile"]["roles"]


def test_sso_callback_oidc_success() -> None:
    """Test POST /api/v1/auth/sso/callback with OIDC claims issues JWT."""
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
    assert res.status_code == 200  # noqa: PLR2004
    data = res.json()
    assert "access_token" in data
    assert data["user_profile"]["email"] == "oidc.user@corp.com"


def test_sso_callback_empty_payload() -> None:
    """Test POST /api/v1/auth/sso/callback with missing payload returns 400."""
    client = TestClient(app)
    res = client.post("/api/v1/auth/sso/callback", json={})
    assert res.status_code == 400  # noqa: PLR2004
    assert "Missing SAMLResponse or OIDC claims" in res.text
