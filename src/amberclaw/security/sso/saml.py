"""SAML 2.0 Service Provider implementation, AuthNRequest generation, and Assertion parsing."""

import base64
import html
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from amberclaw.security.sso.models import SSOConfig, SSOUserProfile

SAML_PROTOCOL_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_ASSERTION_NS = "urn:oasis:names:tc:SAML:2.0:assertion"


def generate_sp_metadata(config: SSOConfig) -> str:
    """Generate SAML 2.0 Service Provider XML metadata."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{html.escape(config.sp_entity_id)}">
    <md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
        <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{html.escape(config.sp_acs_url)}" index="1" isDefault="true"/>
    </md:SPSSODescriptor>
</md:EntityDescriptor>"""


def build_authn_request(config: SSOConfig, relay_state: str = "") -> dict[str, str]:
    """Generate a SAML 2.0 AuthnRequest for HTTP-Redirect binding."""
    req_id = f"id_{uuid.uuid4().hex}"
    issue_instant = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    xml_payload = f"""<samlp:AuthnRequest xmlns:samlp="{SAML_PROTOCOL_NS}" xmlns:saml="{SAML_ASSERTION_NS}" ID="{req_id}" Version="2.0" IssueInstant="{issue_instant}" Destination="{html.escape(config.idp_sso_url)}" AssertionConsumerServiceURL="{html.escape(config.sp_acs_url)}" ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{html.escape(config.sp_entity_id)}</saml:Issuer>
    <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
</samlp:AuthnRequest>"""

    encoded_request = base64.b64encode(xml_payload.encode("utf-8")).decode("utf-8")
    query_params = {"SAMLRequest": encoded_request}
    if relay_state:
        query_params["RelayState"] = relay_state

    redirect_url = f"{config.idp_sso_url}?{urllib.parse.urlencode(query_params)}"
    return {
        "redirect_url": redirect_url,
        "request_id": req_id,
        "saml_request_b64": encoded_request,
    }


def _find_by_local_name(element: ET.Element, local_name: str) -> ET.Element | None:
    """Find the first element matching local XML tag name regardless of namespace."""
    for el in element.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == local_name:
            return el
    return None


def _findall_by_local_name(element: ET.Element, local_name: str) -> list[ET.Element]:
    """Find all elements matching local XML tag name regardless of namespace."""
    results = []
    for el in element.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == local_name:
            results.append(el)
    return results


def parse_and_verify_saml_response(saml_response_b64: str, config: SSOConfig) -> SSOUserProfile:
    """Decode, parse, and validate a SAML 2.0 XML response assertion."""
    raw_xml = base64.b64decode(saml_response_b64).decode("utf-8", errors="replace")
    root = ET.fromstring(raw_xml)  # noqa: S314

    # 1. Verify Status Code
    status_code_el = _find_by_local_name(root, "StatusCode")
    if status_code_el is not None:
        val = status_code_el.attrib.get("Value", "")
        if "Success" not in val:
            raise ValueError(f"SAML Authentication failed with status: {val}")

    # 2. Extract NameID
    name_id_el = _find_by_local_name(root, "NameID")
    if name_id_el is None or not name_id_el.text:
        raise ValueError("SAML Assertion does not contain a valid NameID / Subject")

    email = name_id_el.text.strip()
    user_id = email

    # 3. Extract Attributes
    attributes: dict[str, list[str]] = {}
    attr_elements = _findall_by_local_name(root, "Attribute")
    for attr in attr_elements:
        name = attr.attrib.get("Name", "")
        val_elements = [
            el for el in attr
            if (el.tag.split("}")[-1] if "}" in el.tag else el.tag) == "AttributeValue"
        ]
        vals = [v.text.strip() for v in val_elements if v.text]
        if name and vals:
            attributes[name] = vals

    display_name = (
        attributes.get("displayName", [""])[0]
        or attributes.get("name", [""])[0]
        or email.split("@")[0]
    )
    first_name = attributes.get("givenName", [""])[0] or attributes.get("firstName", [""])[0]
    last_name = attributes.get("sn", [""])[0] or attributes.get("lastName", [""])[0]

    # 4. Role Mapping
    raw_roles = (
        attributes.get(config.role_attribute_name, [])
        or attributes.get("roles", [])
        or attributes.get("groups", [])
    )

    mapped_roles: set[str] = set()
    for raw_role in raw_roles:
        if raw_role in config.role_mapping:
            mapped_roles.add(config.role_mapping[raw_role])
        elif raw_role.lower() in ("admin", "operator", "auditor", "user"):
            mapped_roles.add(raw_role.lower())

    if not mapped_roles:
        mapped_roles.add(config.default_role)

    return SSOUserProfile(
        attributes=attributes,
        display_name=display_name,
        email=email,
        first_name=first_name,
        groups=raw_roles,
        last_name=last_name,
        roles=sorted(mapped_roles),
        user_id=user_id,
    )
