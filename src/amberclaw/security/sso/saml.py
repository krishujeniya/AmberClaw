"""Strict SAML validation through the maintained SAML Python toolkit."""

from typing import Any
from urllib.parse import urlsplit

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings

from amberclaw.security.sso.models import SSOConfig, SSOUserProfile
from amberclaw.security.sso.oidc import validate_oidc_claims


def _settings(config: SSOConfig) -> dict[str, Any]:
    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": config.sp_entity_id,
            "assertionConsumerService": {"url": config.sp_acs_url},
        },
        "idp": {
            "entityId": config.idp_entity_id,
            "singleSignOnService": {"url": config.idp_sso_url},
            "x509cert": config.idp_x509_cert,
        },
        "security": {
            "wantAssertionsSigned": True,
            "wantXMLValidation": True,
            "rejectDeprecatedAlgorithm": True,
            "allowRepeatAttributeName": False,
        },
    }


def _auth(config: SSOConfig, response: str | None = None) -> OneLogin_Saml2_Auth:
    url = urlsplit(config.sp_acs_url)
    if url.scheme != "https" or not url.hostname:
        raise ValueError("SAML callback must use an HTTPS URL")
    if not config.idp_x509_cert:
        raise ValueError("A trusted IdP signing certificate is required")
    return OneLogin_Saml2_Auth(
        {
            "https": "on",
            "http_host": url.netloc,
            "script_name": url.path,
            "get_data": {},
            "post_data": {"SAMLResponse": response} if response else {},
        },
        old_settings=_settings(config),
    )


def generate_sp_metadata(config: SSOConfig) -> str:
    """Generate metadata using the same settings as the assertion verifier."""
    settings = OneLogin_Saml2_Settings(_settings(config), sp_validation_only=True)
    metadata = settings.get_sp_metadata()
    return metadata.decode() if isinstance(metadata, bytes) else str(metadata)


def build_authn_request(config: SSOConfig, relay_state: str = "") -> dict[str, str]:
    """Build a DEFLATE-encoded Redirect-binding request and retain its ID."""
    auth = _auth(config)
    redirect = auth.login(return_to=relay_state)
    return {
        "redirect_url": str(redirect),
        "request_id": str(auth.get_last_request_id()),
    }


def parse_and_verify_saml_response(
    saml_response_b64: str, config: SSOConfig, *, request_id: str | None = None
) -> SSOUserProfile:
    """Verify signatures, schema, issuer, recipient, audience, time and request ID.

    The caller must consume its browser-bound pending request once, before this
    call. Unsolicited assertions are deliberately unsupported.
    """
    if not request_id:
        raise ValueError("A pending SAML authentication request is required")
    auth = _auth(config, saml_response_b64)
    auth.process_response(request_id=request_id)
    if auth.get_errors() or not auth.is_authenticated():
        raise ValueError("SAML assertion verification failed")
    name_id = auth.get_nameid()
    if not isinstance(name_id, str) or not name_id.strip():
        raise ValueError("SAML assertion has no valid subject")
    attributes = auth.get_attributes()
    claims: dict[str, Any] = dict(attributes)
    claims.update({"sub": name_id, "email": name_id})
    for key in ("displayName", "name", "givenName", "sn"):
        values = attributes.get(key, [])
        if values:
            claims[
                {
                    "displayName": "name",
                    "givenName": "given_name",
                    "sn": "family_name",
                }.get(key, key)
            ] = values[0]
    return validate_oidc_claims(claims, config)
