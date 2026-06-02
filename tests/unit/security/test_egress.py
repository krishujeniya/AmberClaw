"""Tests for NetworkPolicy and Egress Controller sandboxing."""

import socket

import pytest

from amberclaw.security import NetworkAccessDenied, NetworkPolicy, egress_sandbox


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
        # Allowed host/port should be fine
        # We wrap this to avoid external network dependencies during tests
        # by checking if it attempts to resolve.
        # BLOCKED hosts must raise NetworkAccessDenied immediately.
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
