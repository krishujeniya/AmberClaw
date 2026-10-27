"""Security penetration tests for Network Egress, SSRF prevention, and Process Isolation."""

import socket
import subprocess
import sys
import pytest

from amberclaw.security.egress_controller import (
    NetworkAccessDenied,
    binary_context,
    egress_sandbox,
    is_private_ip,
)
from amberclaw.security.isolation import (
    ProcessIsolationConfig,
    ResourceLimits,
    get_preexec_isolation_fn,
)
from amberclaw.security.network_policy import NetworkPolicy


def test_ssrf_private_ip_detection():
    """Verify SSRF detection classifies private, loopback, and link-local IPs correctly."""
    # Private IPv4 (RFC 1918)
    assert is_private_ip("127.0.0.1") is True
    assert is_private_ip("10.0.0.1") is True
    assert is_private_ip("172.16.0.1") is True
    assert is_private_ip("172.31.255.255") is True
    assert is_private_ip("192.168.1.100") is True

    # Cloud Metadata Services (AWS/GCP/Azure IMDS)
    assert is_private_ip("169.254.169.254") is True
    assert is_private_ip("169.254.1.1") is True

    # IPv6 Loopback & Link-local
    assert is_private_ip("::1") is True
    assert is_private_ip("fe80::1") is True

    # Public IPs (Must NOT be flagged as private)
    assert is_private_ip("8.8.8.8") is False
    assert is_private_ip("1.1.1.1") is False
    assert is_private_ip("140.82.121.4") is False

    # Invalid input
    assert is_private_ip("not_an_ip") is False


def test_network_policy_wildcard_and_spoof_prevention():
    """Verify wildcard matching permits legitimate subdomains while blocking spoofed domains."""
    policy = NetworkPolicy(
        allowed_hosts=["*.openai.com", "api.anthropic.com", "github.com"],
        allowed_ports=[443],
    )

    # Legitimate subdomains
    assert policy.is_allowed("api.openai.com", 443) is True
    assert policy.is_allowed("platform.openai.com", 443) is True
    assert policy.is_allowed("openai.com", 443) is True
    assert policy.is_allowed("api.anthropic.com", 443) is True
    assert policy.is_allowed("github.com", 443) is True

    # Subdomain spoofing attempts (e.g. attacker registering openai.com.attacker.com)
    assert policy.is_allowed("openai.com.attacker.com", 443) is False
    assert policy.is_allowed("api.openai.com.attacker.com", 443) is False
    assert policy.is_allowed("fake-openai.com", 443) is False
    assert policy.is_allowed("evil-github.com", 443) is False
    assert policy.is_allowed("evil.com", 443) is False


def test_network_policy_tls_enforcement():
    """Verify strict TLS enforcement blocks plaintext HTTP (port 80/8080)."""
    policy = NetworkPolicy(
        allowed_hosts=["api.openai.com"],
        allowed_ports=[80, 443],
        enforce_tls_only=True,
    )

    # HTTPS is allowed
    assert policy.is_allowed("api.openai.com", 443) is True

    # Plaintext HTTP is rejected despite being in allowed_ports
    assert policy.is_allowed("api.openai.com", 80) is False
    assert policy.is_allowed("api.openai.com", 8080) is False


def test_network_policy_binary_confinement():
    """Verify binary-specific egress sandboxing isolates tool network capabilities."""
    policy = NetworkPolicy(
        allowed_hosts=["*"],
        allowed_ports=[443],
        binary_rules={
            "git": {
                "allowed_hosts": ["github.com", "gitlab.com"],
                "allowed_ports": [443],
            },
            "pip": {
                "allowed_hosts": ["pypi.org", "files.pythonhosted.org"],
                "allowed_ports": [443],
            },
        },
    )

    # Git tool context
    assert policy.is_allowed("github.com", 443, binary_context="git") is True
    assert policy.is_allowed("pypi.org", 443, binary_context="git") is False
    assert policy.is_allowed("evil.com", 443, binary_context="git") is False

    # Pip tool context
    assert policy.is_allowed("pypi.org", 443, binary_context="pip") is True
    assert policy.is_allowed("github.com", 443, binary_context="pip") is False


def test_egress_sandbox_runtime_blocking():
    """Verify runtime socket/DNS interception enforces policy in sandboxed context."""
    policy = NetworkPolicy(
        allowed_hosts=["api.openai.com"],
        allowed_ports=[443],
        enforce_tls_only=True,
        binary_rules={
            "git": {
                "allowed_hosts": ["github.com"],
                "allowed_ports": [443],
            },
        },
    )

    with egress_sandbox(policy):
        # 1. Blocked host raises NetworkAccessDenied
        with pytest.raises(NetworkAccessDenied, match="denied by policy"):
            socket.getaddrinfo("unauthorized-host.org", 443)

        # 2. Blocked port (HTTP) raises NetworkAccessDenied
        with pytest.raises(NetworkAccessDenied, match="TLS-only is enforced"):
            socket.getaddrinfo("api.openai.com", 80)

        # 3. Binary context restriction (git is only allowed github.com)
        with binary_context("git"), pytest.raises(NetworkAccessDenied, match="denied by policy"):
            socket.getaddrinfo("api.openai.com", 443)


def test_process_isolation_and_resource_limits():
    """Verify process resource limit configuration and preexec hook generation in subprocess."""
    limits = ResourceLimits(
        max_memory_bytes=256 * 1024 * 1024,
        max_cpu_seconds=15,
        max_open_files=128,
        max_processes=32,
    )

    # Validate execution via independent subprocess to avoid runner pollution
    code = (
        "from amberclaw.security.isolation import ResourceLimits, apply_resource_limits; "
        "apply_resource_limits(ResourceLimits(max_memory_bytes=256*1024*1024)); "
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "OK" in result.stdout

    config = ProcessIsolationConfig(enabled=True, limits=limits)
    preexec_fn = get_preexec_isolation_fn(config)
    assert preexec_fn is not None
    assert callable(preexec_fn)

    # Disabled config returns None
    disabled_cfg = ProcessIsolationConfig(enabled=False)
    assert get_preexec_isolation_fn(disabled_cfg) is None
