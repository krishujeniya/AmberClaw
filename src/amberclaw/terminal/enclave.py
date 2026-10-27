"""Terminal execution backend running in Zero-Trust Hardware and Confidential Enclaves."""

import logging
from pathlib import Path
from typing import Any

from amberclaw.security.enclave.manager import EnclaveManager
from amberclaw.security.enclave.models import EnclaveConfig, EnclavePlatform
from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)


class EnclaveTerminalBackend(BaseTerminalBackend):
    """Terminal execution backend with hardware-rooted remote attestation and encrypted IPC."""

    def __init__(  # noqa: PLR0913
        self,
        workspace_dir: str | Path,
        platform: str = "simulated",
        memory_mb: int = 512,
        vcpu_count: int = 2,
        strict_attestation: bool = True,
        allowed_pcr0_measurements: list[str] | None = None,
        zero_egress: bool = True,
        command_timeout_sec: int = 30,
    ) -> None:
        self.workspace_dir = str(Path(workspace_dir).resolve())
        plat_enum = EnclavePlatform(platform.lower()) if isinstance(platform, str) else platform
        self.config = EnclaveConfig(
            platform=plat_enum,
            memory_mb=memory_mb,
            vcpu_count=vcpu_count,
            strict_attestation=strict_attestation,
            allowed_pcr0_measurements=allowed_pcr0_measurements or [],
            zero_egress=zero_egress,
            command_timeout_sec=command_timeout_sec,
        )
        self.manager = EnclaveManager(config=self.config, workspace_dir=self.workspace_dir)

    async def start(self) -> None:
        """Start and attest the enclave."""
        await self.manager.start()

    async def stop(self) -> None:
        """Stop enclave and zeroize memory."""
        await self.manager.stop()

    async def execute_bash(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Execute bash command inside the attested enclave."""
        if not self.manager.is_ready:
            await self.start()

        res = await self.manager.execute(
            command_type="bash",
            payload=command,
            timeout_sec=timeout,
        )

        return {
            "enclave_id": self.manager.enclave_id,
            "execution_time_ms": res.execution_time_ms,
            "exit_code": res.exit_code,
            "platform": self.config.platform.value,
            "sealed_token": res.sealed_token,
            "stderr": res.stderr,
            "stdout": res.stdout,
        }

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute Python code inside the attested enclave."""
        if not self.manager.is_ready:
            await self.start()

        res = await self.manager.execute(
            command_type="python",
            payload=code,
            env_vars=env or {},
            timeout_sec=timeout,
        )

        return {
            "enclave_id": self.manager.enclave_id,
            "execution_time_ms": res.execution_time_ms,
            "exit_code": res.exit_code,
            "platform": self.config.platform.value,
            "sealed_token": res.sealed_token,
            "stderr": res.stderr,
            "stdout": res.stdout,
        }
