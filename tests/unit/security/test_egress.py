"""Tests for NetworkPolicy and Egress Controller sandboxing."""

import contextlib
import socket

import pytest

from amberclaw.security import NetworkAccessDenied, NetworkPolicy, egress_sandbox
from amberclaw.security.egress_controller import binary_context


def test_network_policy_matching() -> None:
    policy = NetworkPolicy(
        allowed_hosts=[
            "*.openai.com",
            "api.tavily.com",
            "github.com",
        ],
        allowed_ports=[80, 443],
    )

    # Allowed hosts and ports
    assert policy.is_allowed("api.openai.com", 443) is True
    assert policy.is_allowed("openai.com", 80) is True
    assert policy.is_allowed("api.tavily.com", 443) is True
    assert policy.is_allowed("github.com", 443) is True

    # Blocked hosts
    assert policy.is_allowed("google.com", 443) is False
    assert policy.is_allowed("malicious.site", 80) is False

    # Blocked ports
    assert policy.is_allowed("api.openai.com", 8080) is False
    assert policy.is_allowed("github.com", 22) is False


def test_egress_sandbox_intercepts_dns() -> None:
    policy = NetworkPolicy(
        allowed_hosts=["api.openai.com"],
        allowed_ports=[443],
    )

    with egress_sandbox(policy):
        with pytest.raises(NetworkAccessDenied):
            socket.getaddrinfo("google.com", 443)

        with pytest.raises(NetworkAccessDenied):
            socket.getaddrinfo("api.openai.com", 80)  # wrong port


def test_egress_sandbox_intercepts_connect() -> None:
    policy = NetworkPolicy(
        allowed_hosts=["api.openai.com"],
        allowed_ports=[443],
    )

    with egress_sandbox(policy):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(NetworkAccessDenied):
                s.connect(("google.com", 443))
        finally:
            s.close()


def test_egress_sandbox_ssrf_blocking() -> None:
    policy = NetworkPolicy(
        allowed_hosts=["localhost", "127.0.0.1", "api.openai.com"],
        allowed_ports=[80, 443],
    )

    with egress_sandbox(policy):
        # Even if in allowed_hosts, resolving/connecting to private IPs must be blocked by SSRF validation
        with pytest.raises(NetworkAccessDenied, match="SSRF threat detected"):
            socket.getaddrinfo("127.0.0.1", 80)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(NetworkAccessDenied, match="SSRF threat detected"):
                s.connect(("10.0.0.1", 443))
        finally:
            s.close()


def test_egress_sandbox_tls_only_enforcement() -> None:
    policy = NetworkPolicy(
        allowed_hosts=["api.openai.com"],
        allowed_ports=[80, 443],
        enforce_tls_only=True,
    )

    with egress_sandbox(policy), pytest.raises(NetworkAccessDenied, match="TLS-only is enforced"):
        socket.getaddrinfo("api.openai.com", 80)


def test_egress_sandbox_per_binary_restriction() -> None:
    policy = NetworkPolicy(
        allowed_hosts=["api.openai.com"],
        allowed_ports=[443],
        binary_rules={
            "git": {
                "allowed_hosts": ["github.com"],
                "allowed_ports": [443],
            }
        }
    )

    with egress_sandbox(policy):
        # Outside of git binary context, api.openai.com is allowed, github.com is blocked
        assert policy.is_allowed("api.openai.com", 443) is True
        assert policy.is_allowed("github.com", 443) is False

        with binary_context("git"):
            # Inside git context, github.com is allowed, api.openai.com is blocked
            with pytest.raises(NetworkAccessDenied):
                socket.getaddrinfo("api.openai.com", 443)

            # github.com is allowed, but may raise socket error if we try to connect to the actual IP,
            # which is fine as long as it bypasses the firewall check.
            with contextlib.suppress(socket.gaierror):
                socket.getaddrinfo("github.com", 443)
