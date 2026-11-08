"""Ephemeral offline signing identities; no saved private keys or live IdP calls."""

import base64
import uuid
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from amberclaw.security.sso.models import SSOConfig


class SigningIdentity:
    def __init__(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Offline test IdP")])
        now = datetime.now(UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        self.key = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        self.cert = cert.public_bytes(serialization.Encoding.PEM).decode()
        self.public = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def saml_response(
        self,
        config: SSOConfig,
        request_id: str,
        *,
        audience=None,
        recipient=None,
        expires=None,
    ):
        now = datetime.now(UTC)
        issued = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        before = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        expiry = (expires or now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        saml = "urn:oasis:names:tc:SAML:2.0:assertion"
        protocol = "urn:oasis:names:tc:SAML:2.0:protocol"
        root = etree.Element(
            f"{{{protocol}}}Response",
            nsmap={"samlp": protocol, "saml": saml},
            ID=f"id_{uuid.uuid4().hex}",
            Version="2.0",
            IssueInstant=issued,
            Destination=config.sp_acs_url,
            InResponseTo=request_id,
        )
        etree.SubElement(root, f"{{{saml}}}Issuer").text = config.idp_entity_id
        status = etree.SubElement(root, f"{{{protocol}}}Status")
        etree.SubElement(
            status,
            f"{{{protocol}}}StatusCode",
            Value="urn:oasis:names:tc:SAML:2.0:status:Success",
        )
        assertion = etree.Element(
            f"{{{saml}}}Assertion",
            nsmap={"saml": saml},
            ID=f"id_{uuid.uuid4().hex}",
            Version="2.0",
            IssueInstant=issued,
        )
        etree.SubElement(assertion, f"{{{saml}}}Issuer").text = config.idp_entity_id
        subject = etree.SubElement(assertion, f"{{{saml}}}Subject")
        etree.SubElement(subject, f"{{{saml}}}NameID").text = "signed.user@example.com"
        confirmation = etree.SubElement(
            subject,
            f"{{{saml}}}SubjectConfirmation",
            Method="urn:oasis:names:tc:SAML:2.0:cm:bearer",
        )
        etree.SubElement(
            confirmation,
            f"{{{saml}}}SubjectConfirmationData",
            Recipient=recipient or config.sp_acs_url,
            InResponseTo=request_id,
            NotOnOrAfter=expiry,
        )
        conditions = etree.SubElement(
            assertion, f"{{{saml}}}Conditions", NotBefore=before, NotOnOrAfter=expiry
        )
        restriction = etree.SubElement(conditions, f"{{{saml}}}AudienceRestriction")
        etree.SubElement(restriction, f"{{{saml}}}Audience").text = (
            audience or config.sp_entity_id
        )
        statement = etree.SubElement(
            assertion,
            f"{{{saml}}}AuthnStatement",
            AuthnInstant=issued,
            SessionIndex="offline-session",
        )
        context = etree.SubElement(statement, f"{{{saml}}}AuthnContext")
        etree.SubElement(
            context, f"{{{saml}}}AuthnContextClassRef"
        ).text = "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
        attributes = etree.SubElement(assertion, f"{{{saml}}}AttributeStatement")
        attribute = etree.SubElement(attributes, f"{{{saml}}}Attribute", Name="roles")
        etree.SubElement(
            attribute, f"{{{saml}}}AttributeValue"
        ).text = "AmberClaw-Admins"
        signed = OneLogin_Saml2_Utils.add_sign(
            etree.tostring(assertion), self.key, self.cert
        )
        root.append(etree.fromstring(signed))
        return base64.b64encode(etree.tostring(root)).decode()
