"""Unit tests for EnclaveTerminalBackend and factory registration."""

import tempfile
from pathlib import Path

import pytest

from amberclaw.terminal.enclave import EnclaveTerminalBackend
from amberclaw.terminal.factory import BackendFactory


@pytest.mark.asyncio
async def test_enclave_backend_python_execution() -> None:
    """Test EnclaveTerminalBackend execute_python with environment variables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = EnclaveTerminalBackend(
            workspace_dir=tmpdir,
            platform="simulated",
            memory_mb=256,
            vcpu_count=2,
            strict_attestation=True,
        )

        await backend.start()

        code = """
import os
print("SECRET_VAR:", os.environ.get("AGENT_SECRET"))
print("STATUS: RUNNING_IN_ENCLAVE")
"""
        res = await backend.execute_python(
            code=code,
            env={"AGENT_SECRET": "amberclaw-enclave-passphrase-999"},
        )

        assert res["exit_code"] == 0
        assert "SECRET_VAR: amberclaw-enclave-passphrase-999" in res["stdout"]
        assert "STATUS: RUNNING_IN_ENCLAVE" in res["stdout"]
        assert "sealed_token" in res
        assert res["platform"] == "simulated"
        assert res["execution_time_ms"] > 0

        await backend.stop()


@pytest.mark.asyncio
async def test_enclave_backend_bash_execution() -> None:
    """Test EnclaveTerminalBackend execute_bash commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = EnclaveTerminalBackend(workspace_dir=tmpdir)

        res = await backend.execute_bash("echo 'zero trust enclave bash'")
        assert res["exit_code"] == 0
        assert "zero trust enclave bash" in res["stdout"].strip()
        assert len(res["sealed_token"]) > 0

        # File creation and verification inside workspace
        res_file = await backend.execute_bash("echo 'payload' > enclave_file.txt && cat enclave_file.txt")
        assert res_file["exit_code"] == 0
        assert "payload" in res_file["stdout"]
        assert (Path(tmpdir) / "enclave_file.txt").exists()

        await backend.stop()


@pytest.mark.asyncio
async def test_enclave_backend_timeout() -> None:
    """Test timeout enforcement in EnclaveTerminalBackend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = EnclaveTerminalBackend(workspace_dir=tmpdir)

        res = await backend.execute_bash("sleep 5", timeout=1)
        assert res["exit_code"] == -9  # noqa: PLR2004
        assert "timed out" in res["stderr"].lower()

        await backend.stop()


def test_factory_enclave_backend_creation() -> None:
    """Test BackendFactory dynamically instantiates EnclaveTerminalBackend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = BackendFactory.create_backend(
            "enclave",
            workspace_dir=tmpdir,
            platform="nitro",
            memory_mb=1024,
            vcpu_count=4,
            strict_attestation=True,
        )

        assert isinstance(backend, EnclaveTerminalBackend)
        assert backend.config.platform.value == "nitro"
        assert backend.config.memory_mb == 1024  # noqa: PLR2004
        assert backend.config.vcpu_count == 4  # noqa: PLR2004
        assert backend.config.strict_attestation is True


@pytest.mark.asyncio
async def test_enclave_backend_strict_attestation_failure() -> None:
    """Test EnclaveTerminalBackend raises on invalid attestation whitelist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = EnclaveTerminalBackend(
            workspace_dir=tmpdir,
            strict_attestation=True,
            allowed_pcr0_measurements=["unmatched-pcr0-hash-000000000000000000000000"],
        )

        with pytest.raises(RuntimeError, match="Zero-Trust Enclave Attestation Failed"):
            await backend.start()
