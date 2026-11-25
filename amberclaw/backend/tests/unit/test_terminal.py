# ruff: noqa: PLR2004, S106
"""Unit tests for AmberClaw Terminal execution backends and BackendFactory."""

from pathlib import Path

import pytest

from amberclaw.terminal.base import BaseTerminalBackend
from amberclaw.terminal.daytona import DaytonaTerminalBackend
from amberclaw.terminal.docker import DockerTerminalBackend
from amberclaw.terminal.e2b import E2BTerminalBackend
from amberclaw.terminal.enclave import EnclaveTerminalBackend
from amberclaw.terminal.factory import BackendFactory
from amberclaw.terminal.local import LocalTerminalBackend
from amberclaw.terminal.modal import ModalTerminalBackend
from amberclaw.terminal.singularity import SingularityTerminalBackend
from amberclaw.terminal.ssh import SSHTerminalBackend
from amberclaw.terminal.vercel import VercelTerminalBackend
from amberclaw.terminal.wasm import WasmTerminalBackend

# ==============================================================================
# 1. BackendFactory Instantiation Across All 10 Sandboxes
# ==============================================================================


def test_factory_creates_local_backend(tmp_path: Path):
    backend = BackendFactory.create_backend("local", workspace_dir=str(tmp_path))
    assert isinstance(backend, LocalTerminalBackend)
    assert isinstance(backend, BaseTerminalBackend)
    assert backend.sandbox.workspace == tmp_path


def test_factory_creates_docker_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "docker", workspace_dir=str(tmp_path), image="python:3.11-alpine"
    )
    assert isinstance(backend, DockerTerminalBackend)
    assert backend.image == "python:3.11-alpine"


def test_factory_creates_ssh_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "ssh", workspace_dir=str(tmp_path), host="remote.host.internal", port=2222
    )
    assert isinstance(backend, SSHTerminalBackend)
    assert backend.host == "remote.host.internal"
    assert backend.port == 2222


def test_factory_creates_wasm_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "wasm", workspace_dir=str(tmp_path), memory_bytes=65536
    )
    assert isinstance(backend, WasmTerminalBackend)


def test_factory_creates_e2b_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "e2b", workspace_dir=str(tmp_path), api_key="e2b_test_key"
    )
    assert isinstance(backend, E2BTerminalBackend)


def test_factory_creates_daytona_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "daytona", workspace_dir=str(tmp_path), api_key="daytona_key_123"
    )
    assert isinstance(backend, DaytonaTerminalBackend)


def test_factory_creates_modal_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "modal", workspace_dir=str(tmp_path), app_name="amberclaw-modal-app"
    )
    assert isinstance(backend, ModalTerminalBackend)


def test_factory_creates_singularity_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "singularity", workspace_dir=str(tmp_path), image="library://default"
    )
    assert isinstance(backend, SingularityTerminalBackend)


def test_factory_creates_vercel_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "vercel", workspace_dir=str(tmp_path), token="vc_tok_123"
    )
    assert isinstance(backend, VercelTerminalBackend)


def test_factory_creates_enclave_backend(tmp_path: Path):
    backend = BackendFactory.create_backend(
        "enclave", workspace_dir=str(tmp_path), enclave_type="nitro"
    )
    assert isinstance(backend, EnclaveTerminalBackend)


def test_factory_rejects_unknown_backend(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown terminal backend type"):
        BackendFactory.create_backend("quantum_hypervisor", workspace_dir=str(tmp_path))


# ==============================================================================
# 2. Local Terminal Execution & Timeouts
# ==============================================================================


@pytest.mark.asyncio
async def test_local_terminal_run_command_success(tmp_path: Path):
    backend = LocalTerminalBackend(workspace_dir=str(tmp_path))

    result = await backend.execute_bash("echo 'AmberClaw Terminal Active'")
    assert result["exit_code"] == 0
    assert "AmberClaw Terminal Active" in result["stdout"]


@pytest.mark.asyncio
async def test_local_terminal_captures_stderr(tmp_path: Path):
    backend = LocalTerminalBackend(workspace_dir=str(tmp_path))

    result = await backend.execute_bash("sh -c 'echo \"simulated error\" >&2; exit 42'")
    assert result["exit_code"] == 42
    assert "simulated error" in result["stderr"]


@pytest.mark.asyncio
async def test_local_terminal_respects_workspace_context(tmp_path: Path):
    backend = LocalTerminalBackend(workspace_dir=str(tmp_path))
    test_file = tmp_path / "hello.txt"
    test_file.write_text("content in workspace", encoding="utf-8")

    result = await backend.execute_bash(f"cat {test_file}")
    assert result["exit_code"] == 0
    assert "content in workspace" in result["stdout"]


@pytest.mark.asyncio
async def test_local_terminal_execute_python(tmp_path: Path):
    backend = LocalTerminalBackend(workspace_dir=str(tmp_path))
    code = "print(2 + 2 * 10)"

    result = await backend.execute_python(code)
    assert result["exit_code"] == 0
    assert "22" in result["stdout"]
