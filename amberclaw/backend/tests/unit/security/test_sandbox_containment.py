"""Containment attestation, strict fail-closed, and escape resistance tests (CL-006 / A06)."""

import platform
from unittest.mock import MagicMock, patch

import pytest

from amberclaw.security.sandbox import (
    CodeSandbox,
    ContainmentAttestation,
    DecompressionGuard,
    DecompressionSecurityError,
    EphemeralFilesystemSandbox,
    HostSocketAndMetadataFilter,
    SandboxContainmentError,
    SandboxEscapeTestRunner,
    apply_sandbox_to_current_process,
    probe_containment_capabilities,
)


def test_probe_containment_capabilities():
    att = probe_containment_capabilities()
    assert isinstance(att, ContainmentAttestation)
    assert att.os == platform.system()
    assert att.kernel == platform.release()
    assert att.arch == platform.machine()
    assert not att.strict


def test_strict_mode_refuses_execution_when_namespace_fails(tmp_path):
    mock_libc = MagicMock()
    mock_libc.unshare.return_value = -1

    with patch("ctypes.CDLL", return_value=mock_libc), \
         patch("resource.setrlimit"):
        with pytest.raises(SandboxContainmentError) as exc_info:
            apply_sandbox_to_current_process(tmp_path, block_execve=False, strict=True)
        assert "Namespace isolation" in str(exc_info.value)


def test_strict_mode_refuses_execution_when_landlock_fails(tmp_path):
    mock_libc = MagicMock()
    mock_libc.unshare.return_value = 0
    mock_libc.prctl.return_value = 0

    with patch("ctypes.CDLL", return_value=mock_libc), \
         patch("resource.setrlimit"), \
         patch("amberclaw.security.landlock.apply_sandbox", return_value=False):
        with pytest.raises(SandboxContainmentError) as exc_info:
            apply_sandbox_to_current_process(tmp_path, block_execve=False, strict=True)
        assert "Landlock LSM filesystem containment is not supported" in str(exc_info.value)


def test_degraded_mode_records_landlock_limitation_without_raising(tmp_path):
    mock_libc = MagicMock()
    mock_libc.unshare.return_value = 0
    mock_libc.prctl.return_value = 0

    with patch("ctypes.CDLL", return_value=mock_libc), \
         patch("resource.setrlimit"), \
         patch("amberclaw.security.landlock.apply_sandbox", return_value=False):
        attestation = apply_sandbox_to_current_process(tmp_path, block_execve=False, strict=False)
        assert not attestation.landlock_active
        assert any("Landlock LSM" in lim for lim in attestation.limitations)
        assert not attestation.fully_contained


def test_strict_mode_refuses_execution_when_seccomp_fails(tmp_path):
    mock_libc = MagicMock()
    mock_libc.unshare.return_value = 0
    mock_libc.prctl.return_value = 0

    with patch("ctypes.CDLL", return_value=mock_libc), \
         patch("resource.setrlimit"), \
         patch("amberclaw.security.landlock.apply_sandbox", return_value=True), \
         patch("amberclaw.security.sandbox.apply_seccomp_filters", return_value=False):
        with pytest.raises(SandboxContainmentError) as exc_info:
            apply_sandbox_to_current_process(tmp_path, block_execve=True, strict=True)
        assert "Seccomp filter enforcement failed" in str(exc_info.value)


def test_strict_mode_refuses_execution_on_non_linux(tmp_path):
    with patch("platform.system", return_value="Darwin"):
        with pytest.raises(SandboxContainmentError) as exc_info:
            apply_sandbox_to_current_process(tmp_path, strict=True)
        assert "does not support Linux kernel containment" in str(exc_info.value)


def test_codesandbox_attest_containment_method(tmp_path):
    sandbox = CodeSandbox(use_docker=False, workspace=tmp_path)
    att = sandbox.attest_containment()
    assert isinstance(att, ContainmentAttestation)
    assert att.os == platform.system()


def test_host_socket_and_metadata_filter_containment_probes():
    # 1. Host Docker socket access
    assert HostSocketAndMetadataFilter.is_host_socket_path("/var/run/docker.sock")
    assert HostSocketAndMetadataFilter.is_host_socket_path("/run/containerd/containerd.sock")
    assert not HostSocketAndMetadataFilter.is_host_socket_path("/home/user/app.sock")

    # 2. Link-local and cloud metadata IPs
    assert HostSocketAndMetadataFilter.is_forbidden_ip("169.254.169.254")
    assert HostSocketAndMetadataFilter.is_forbidden_ip("127.0.0.1")
    assert HostSocketAndMetadataFilter.is_forbidden_ip("10.0.0.1")
    assert not HostSocketAndMetadataFilter.is_forbidden_ip("8.8.8.8")

    # 3. Hostnames
    assert not HostSocketAndMetadataFilter.verify_destination_host("metadata.google.internal")
    assert not HostSocketAndMetadataFilter.verify_destination_host("169.254.169.254")


def test_ephemeral_filesystem_path_traversal_denied():
    with EphemeralFilesystemSandbox() as sandbox:
        assert sandbox.path is not None
        safe_child = sandbox.resolve_safe_path("subdir/nested.txt")
        assert sandbox.path in safe_child.parents

        with pytest.raises(PermissionError) as exc_info:
            sandbox.resolve_safe_path("../../etc/shadow")
        assert "Path traversal detected" in str(exc_info.value)


def test_decompression_guard_rejects_zip_slip_and_bombs(tmp_path):
    import io
    import zipfile

    # Build zip-slip archive in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/cron.d/malicious", "malicious payload")
    buf.seek(0)

    extract_dir = tmp_path / "extracted"
    with pytest.raises(DecompressionSecurityError) as exc_info:
        DecompressionGuard.extract_zip(buf, extract_dir)
    assert "Zip-slip directory traversal attempt detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_automated_sandbox_escape_runner():
    runner = SandboxEscapeTestRunner(CodeSandbox(use_docker=False))
    results = await runner.run_all_checks()
    assert "host_socket_blocked" in results
    assert results["host_socket_blocked"] is True
    assert "cloud_metadata_blocked" in results
    assert results["cloud_metadata_blocked"] is True
    assert "private_ip_blocked" in results
    assert results["private_ip_blocked"] is True
