from typing import Any

from amberclaw.security.sandbox import CodeSandbox
from amberclaw.terminal.base import BaseTerminalBackend


class LocalTerminalBackend(BaseTerminalBackend):
    """Local execution backend that wraps CodeSandbox with local secure sandbox."""

    def __init__(self, workspace_dir: str):
        self.sandbox = CodeSandbox(use_docker=False, workspace=workspace_dir)

    async def execute_bash(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        self.sandbox.default_timeout_sec = timeout
        res = await self.sandbox.execute_bash(command)
        return res.model_dump()

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.sandbox.default_timeout_sec = timeout
        res = await self.sandbox.execute_python(code, env_vars=env)
        return res.model_dump()
