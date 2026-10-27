"""Unit tests for SAML 2.0 and OIDC Enterprise Single Sign-On."""

import base64

import pytest

from amberclaw.security.sso.models import SSOConfig, SSOProtocol
from amberclaw.security.sso.oidc import build_oidc_auth_url, validate_oidc_claims
from amberclaw.security.sso.saml import (
    build_authn_request,
    generate_sp_metadata,
    parse_and_verify_saml_response,
)


def test_saml_metadata_generation() -> None:
    """Test SAML 2.0 SP XML metadata structure."""
    config = SSOConfig(
        sp_entity_id="https://amberclaw.ai/sp/metadata",
        sp_acs_url="https://amberclaw.ai/api/v1/auth/sso/callback",
    )
    metadata_xml = generate_sp_metadata(config)
    assert "<md:EntityDescriptor" in metadata_xml
    assert 'entityID="https://amberclaw.ai/sp/metadata"' in metadata_xml
    assert 'Location="https://amberclaw.ai/api/v1/auth/sso/callback"' in metadata_xml


def test_saml_authn_request_builder() -> None:
    """Test building SAML AuthnRequest with redirect URL."""
    config = SSOConfig(idp_sso_url="https://idp.okta.com/app/amberclaw/sso/saml")
    result = build_authn_request(config, relay_state="/dashboard")
    assert "redirect_url" in result
    assert "https://idp.okta.com/app/amberclaw/sso/saml?SAMLRequest=" in result["redirect_url"]
    assert "RelayState=%2Fdashboard" in result["redirect_url"]
    assert len(result["request_id"]) > 0


def test_saml_response_parsing_and_role_mapping() -> None:
    """Test parsing a valid SAML 2.0 XML assertion."""
    config = SSOConfig(
        role_mapping={"AmberClaw-Admins": "admin", "Engineers": "operator"},
        default_role="user",
    )

    saml_xml = """<?xml version="1.0"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" Version="2.0">
    <samlp:Status>
        <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
    </samlp:Status>
    <saml:Assertion Version="2.0">
        <saml:Subject>
            <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">alice.engineer@enterprise.com</saml:NameID>
        </saml:Subject>
        <saml:AttributeStatement>
            <saml:Attribute Name="displayName">
                <saml:AttributeValue>Alice Engineer</saml:AttributeValue>
            </saml:Attribute>
            <saml:Attribute Name="roles">
                <saml:AttributeValue>AmberClaw-Admins</saml:AttributeValue>
                <saml:AttributeValue>Engineers</saml:AttributeValue>
            </saml:Attribute>
        </saml:AttributeStatement>
    </saml:Assertion>
</samlp:Response>"""

    b64_response = base64.b64encode(saml_xml.encode("utf-8")).decode("utf-8")
    profile = parse_and_verify_saml_response(b64_response, config)

    assert profile.email == "alice.engineer@enterprise.com"
    assert profile.user_id == "alice.engineer@enterprise.com"
    assert profile.display_name == "Alice Engineer"
    assert "admin" in profile.roles
    assert "operator" in profile.roles


def test_saml_response_failure_status() -> None:
    """Test SAML response with non-success status raises ValueError."""
    config = SSOConfig()
    saml_xml = """<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">
    <samlp:Status>
        <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:AuthnFailed"/>
    </samlp:Status>
</samlp:Response>"""

    b64 = base64.b64encode(saml_xml.encode("utf-8")).decode("utf-8")
    with pytest.raises(ValueError, match="SAML Authentication failed with status"):
        parse_and_verify_saml_response(b64, config)


def test_oidc_auth_url_and_claims_validation() -> None:
    """Test OIDC auth redirect construction and ID token claims extraction."""
    config = SSOConfig(
        protocol=SSOProtocol.OIDC,
        oidc_issuer_url="https://auth.company.com",
        oidc_client_id="amberclaw-client-id",
        role_mapping={"SecOps": "auditor"},
    )

    url = build_oidc_auth_url(config, state="state_123", nonce="nonce_456")
    assert "https://auth.company.com/protocol/openid-connect/auth?" in url
    assert "client_id=amberclaw-client-id" in url

    claims = {
        "sub": "user_oidc_9988",
        "email": "bob@company.com",
        "name": "Bob Security",
        "roles": ["SecOps"],
    }

    profile = validate_oidc_claims(claims, config)
    assert profile.user_id == "user_oidc_9988"
    assert profile.email == "bob@company.com"
    assert profile.display_name == "Bob Security"
    assert "auditor" in profile.roles
