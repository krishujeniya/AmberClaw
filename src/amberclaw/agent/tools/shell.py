"""Shell execution tool."""

import asyncio
import os
import platform
import re
import signal
from contextlib import suppress
from pathlib import Path

from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


class ExecArgs(BaseModel):
    """Arguments for the shell execution tool."""

    command: str = Field(..., description="The shell command to execute")
    working_dir: str | None = Field(
        None,
        description="Optional working directory for the command",
    )


class ExecTool(PydanticTool):
    """Tool to execute shell commands."""

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."

    @property
    def args_schema(self) -> type[ExecArgs]:
        return ExecArgs

    def __init__(  # noqa: PLR0913 - retain the public execution policy keyword contract
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = True,
        path_append: str = "",
        restricted_paths: list[str] | None = None,
        allow_network_egress: bool | None = None,
    ) -> None:
        super().__init__()
        self.timeout = timeout
        self.working_dir = working_dir
        self.deny_patterns = (
            deny_patterns
            if deny_patterns is not None
            else [
                r"\brm\s+-[rf]{1,2}\b",  # rm -r, rm -rf, rm -fr
                r"\bdel\s+/[fq]\b",  # del /f, del /q
                r"\brmdir\s+/s\b",  # rmdir /s
                r"(?:^|[;&|]\s*)format\b",  # format (as standalone command only)
                r"\b(mkfs|diskpart)\b",  # disk operations
                r"\bdd\s+if=",  # dd
                r">\s*/dev/sd",  # write to disk
                r"\b(shutdown|reboot|poweroff)\b",  # system power
                r":\(\)\s*\{.*\};\s*:",  # fork bomb
            ]
        )
        self.allow_patterns = allow_patterns if allow_patterns is not None else []
        self.restrict_to_workspace = restrict_to_workspace
        self.path_append = path_append
        self.restricted_paths = restricted_paths
        self.allow_network_egress = allow_network_egress

    async def run(self, args: ExecArgs) -> str:
        cwd = (
            args.working_dir
            or self.working_dir
            or str(await asyncio.to_thread(Path.cwd))
        )
        guard_error = self._guard_command(args.command, cwd)
        if guard_error:
            return guard_error

        env = os.environ.copy()
        if self.path_append:
            env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append

        preexec = None
        if self.restrict_to_workspace and platform.system() == "Linux":
            from amberclaw.security.landlock import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                apply_sandbox,
            )

            workspace_dir = str(await asyncio.to_thread(Path(cwd).resolve))

            def _sandbox_preexec() -> None:
                apply_sandbox(workspace_dir)

            preexec = _sandbox_preexec

        try:
            process = await asyncio.create_subprocess_shell(
                args.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                preexec_fn=preexec,
                start_new_session=os.name == "posix",
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except TimeoutError:
                await self._terminate_process(process)
                return f"Error: Command timed out after {self.timeout} seconds"
            except asyncio.CancelledError:
                await self._terminate_process(process)
                raise

            output_parts = []

            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))

            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")

            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"

            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = (
                    result[:max_len]
                    + f"\n... (truncated, {len(result) - max_len} more chars)"
                )

            return result

        except Exception as e:
            return f"Error executing command: {e!s}"

    @staticmethod
    async def _terminate_process(process: asyncio.subprocess.Process) -> None:
        # The shell owns a new POSIX session. Kill its descendants even if the
        # shell already exited while a child retained its output pipes.
        with suppress(ProcessLookupError):
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        with suppress(TimeoutError):
            await asyncio.wait_for(process.communicate(), timeout=5.0)

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        lower = cmd.lower()

        # Check restricted paths policy
        restricted = self.restricted_paths
        if restricted is None:
            try:
                from amberclaw.config.schema import settings  # noqa: PLC0415

                restricted = getattr(settings.security, "restricted_paths", None)
            except Exception:
                restricted = None

        if restricted:
            for raw in self._extract_absolute_paths(command):
                try:
                    p = Path(raw.strip()).expanduser().resolve()
                    for rp in restricted:
                        rp_p = Path(rp).expanduser().resolve()
                        if p == rp_p or rp_p in p.parents:
                            return f"Error: Command blocked by safety guard (access to restricted path '{raw}')"
                except Exception:
                    continue

        # Check network egress policy
        egress_allowed = self.allow_network_egress
        if egress_allowed is None:
            try:
                from amberclaw.config.schema import settings  # noqa: PLC0415

                egress_allowed = getattr(settings.security, "allow_network_egress", True)
            except Exception:
                egress_allowed = True

        if not egress_allowed:
            network_commands = [
                r"\bcurl\b",
                r"\bwget\b",
                r"\bnc\b",
                r"\bnetcat\b",
                r"\bssh\b",
                r"\bscp\b",
                r"\bping\b",
                r"\btelnet\b",
                r"\bftp\b",
                r"\bnmap\b",
            ]
            for pat in network_commands:
                if re.search(pat, lower):
                    return "Error: Command blocked by security policy (network egress is disabled)"

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        if self.allow_patterns and not any(
            re.search(p, lower) for p in self.allow_patterns
        ):
            return "Error: Command blocked by safety guard (not in allowlist)"

        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return (
                    "Error: Command blocked by safety guard (path traversal detected)"
                )

            return self._guard_paths(cmd, cwd)

        return None

    def _guard_paths(self, command: str, cwd: str) -> str | None:
        try:
            cwd_path = Path(cwd).resolve()
            for raw in self._extract_absolute_paths(command):
                path = Path(raw.strip()).resolve()
                if path.is_absolute() and not path.is_relative_to(cwd_path):
                    return "Error: Command blocked by safety guard (path outside working dir)"
        except (OSError, RuntimeError, ValueError):
            return "Error: Command blocked by safety guard (unresolvable path or working directory)"
        return None

    @staticmethod
    def _extract_absolute_paths(command: str) -> list[str]:
        win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)  # Windows: C:\...
        posix_paths = re.findall(
            r"(?:^|[\s|>])(/[^\s\"'>]+)", command
        )  # POSIX: /absolute only
        return win_paths + posix_paths
