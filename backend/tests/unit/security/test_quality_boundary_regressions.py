"""Offline regressions for security boundaries and stdlib socket contracts."""

import errno
import json
import socket
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from amberclaw.security import egress_controller as egress
from amberclaw.security.filters import ToolExecutionFilter
from amberclaw.security.network_policy import NetworkPolicy
from amberclaw.security.pii import PIIRedactor
from amberclaw.security.sandbox import HostSocketAndMetadataFilter
from amberclaw.security.vault import SecretVault


@pytest.fixture
def active_policy():
    policy = NetworkPolicy(
        allowed_hosts=["example.com", "8.8.8.8"], allowed_ports=[443]
    )
    active = egress._egress_active.set(True)
    token = egress._egress_policy.set(policy)
    try:
        yield policy
    finally:
        egress._egress_policy.reset(token)
        egress._egress_active.reset(active)


def test_output_filter_redacts_pii(monkeypatch):
    monkeypatch.setattr(PIIRedactor, "__init__", lambda _self: None)
    monkeypatch.setattr(PIIRedactor, "redact", lambda _self, _text: "[REDACTED_EMAIL]")
    assert (
        ToolExecutionFilter.filter_output("search", "a@example.com", redact_pii=True)
        == "[REDACTED_EMAIL]"
    )


@pytest.mark.usefixtures("active_policy")
def test_bytes_dns_host_obeys_policy(monkeypatch):
    resolver = Mock(
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
    )
    monkeypatch.setattr(egress, "_original_getaddrinfo", resolver)
    assert egress.patched_getaddrinfo(b"example.com", b"443")
    resolver.assert_called_once()


@pytest.mark.usefixtures("active_policy")
def test_missing_dns_host_is_denied_before_resolution(monkeypatch):
    resolver = Mock()
    monkeypatch.setattr(egress, "_original_getaddrinfo", resolver)
    with pytest.raises(egress.NetworkAccessDenied):
        egress.patched_getaddrinfo(None, 443)
    resolver.assert_not_called()


@pytest.mark.usefixtures("active_policy")
def test_non_ip_dns_result_is_denied(monkeypatch):
    monkeypatch.setattr(
        egress,
        "_original_getaddrinfo",
        Mock(
            return_value=[
                (socket.AF_UNIX, socket.SOCK_STREAM, 0, "", (134744072, b"unix"))
            ]
        ),
    )
    with pytest.raises(egress.NetworkAccessDenied):
        egress.patched_getaddrinfo("example.com", 443)


@pytest.mark.usefixtures("active_policy")
def test_unix_socket_is_denied_explicitly(monkeypatch):
    connector = Mock()
    monkeypatch.setattr(egress, "_original_connect", connector)
    with (
        socket.socket(socket.AF_UNIX) as sock,
        pytest.raises(egress.NetworkAccessDenied),
    ):
        egress.patched_connect(sock, "/var/run/docker.sock")
    connector.assert_not_called()


@pytest.mark.usefixtures("active_policy")
def test_connect_ex_preserves_errno(monkeypatch):
    monkeypatch.setattr(
        egress,
        "_original_connect",
        Mock(side_effect=OSError(errno.ECONNREFUSED, "refused")),
    )
    original = Mock(return_value=errno.ECONNREFUSED)
    monkeypatch.setattr(egress, "_original_connect_ex", original)
    with socket.socket() as sock:
        assert egress.patched_connect_ex(sock, ("8.8.8.8", 443)) == errno.ECONNREFUSED
    original.assert_called_once()


def test_host_filter_rejects_non_ip_sockaddr(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        Mock(
            return_value=[
                (socket.AF_UNIX, socket.SOCK_STREAM, 0, "", (134744072, b"unix"))
            ]
        ),
    )
    assert HostSocketAndMetadataFilter.verify_destination_host("example.com") is False


@pytest.mark.parametrize("payload", [["token"], {"token": 123}, None])
def test_vault_rejects_non_string_mapping(tmp_path, payload):
    vault = SecretVault(key_dir=tmp_path)
    vault.vault_file.write_bytes(
        vault._get_fernet().encrypt(json.dumps(payload).encode())
    )
    assert vault._load_vault_data() == {}


@pytest.mark.usefixtures("active_policy")
def test_direct_hostname_cannot_bypass_private_dns_check(monkeypatch):
    connector = Mock()
    monkeypatch.setattr(egress, "_original_connect", connector)
    monkeypatch.setattr(
        egress,
        "_original_getaddrinfo",
        Mock(
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
            ]
        ),
    )
    with socket.socket() as sock, pytest.raises(egress.NetworkAccessDenied):
        egress.patched_connect(sock, ("example.com", 443))
    connector.assert_not_called()


@pytest.mark.usefixtures("active_policy")
def test_direct_hostname_pins_verified_address(monkeypatch):
    connector = Mock()
    monkeypatch.setattr(egress, "_original_connect", connector)
    monkeypatch.setattr(
        egress,
        "_original_getaddrinfo",
        Mock(
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        ),
    )
    with socket.socket() as sock:
        egress.patched_connect(sock, ("example.com", 443))
        connector.assert_called_once_with(sock, ("8.8.8.8", 443))


def test_presidio_non_string_output_falls_back_to_regex(monkeypatch):
    entities = ModuleType("presidio_anonymizer.entities")
    monkeypatch.setattr(entities, "OperatorConfig", Mock(), raising=False)
    monkeypatch.setitem(sys.modules, "presidio_anonymizer.entities", entities)
    redactor = PIIRedactor()
    redactor.presidio_available = True
    redactor._analyzer = Mock()
    redactor._anonymizer = Mock()
    redactor._anonymizer.anonymize.return_value = SimpleNamespace(text=123)
    assert redactor.redact("email a@example.com") == "email [REDACTED_EMAIL]"


def test_presidio_direct_call_without_engines_fails_explicitly(monkeypatch):
    entities = ModuleType("presidio_anonymizer.entities")
    monkeypatch.setattr(entities, "OperatorConfig", Mock(), raising=False)
    monkeypatch.setitem(sys.modules, "presidio_anonymizer.entities", entities)
    redactor = PIIRedactor()
    redactor._analyzer = None
    redactor._anonymizer = None
    with pytest.raises(RuntimeError, match="unavailable"):
        redactor._redact_presidio("email a@example.com")
