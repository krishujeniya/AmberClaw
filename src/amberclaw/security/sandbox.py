import asyncio
import contextlib
import ctypes
import logging
import os
import platform
import resource
import sys
import tempfile
import uuid
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Constants for namespace isolation
CLONE_NEWUSER = 0x10000000
CLONE_NEWNET = 0x40000000
CLONE_NEWNS = 0x00020000
CLONE_NEWIPC = 0x08000000
CLONE_NEWUTS = 0x04000000

# Seccomp Constants
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
BPF_LD = 0x00
BPF_W = 0x00
BPF_ABS = 0x20
BPF_JMP = 0x05
BPF_JEQ = 0x15
BPF_K = 0x00
BPF_RET = 0x06
SECCOMP_RET_ALLOW = 0x7fff0000
SECCOMP_RET_ERRNO = 0x00050000
EACCES = 13
AUDIT_ARCH_X86_64 = 0xC000003E
SYS_execve = 59
SYS_ptrace = 101


class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float


def apply_seccomp_filters() -> bool:
    """Applies seccomp filters to block execve and ptrace syscalls."""
    if platform.system() != "Linux":
        return False

    arch = platform.machine()
    if arch == "x86_64":
        sys_execve = 59
        sys_ptrace = 101
        audit_arch = 0xC000003E
    elif arch in ("aarch64", "arm64"):
        sys_execve = 221
        sys_ptrace = 117
        audit_arch = 0xC00000B7
    else:
        return False

    class SockFilter(ctypes.Structure):
        _fields_ = [
            ("code", ctypes.c_ushort),
            ("jt", ctypes.c_ubyte),
            ("jf", ctypes.c_ubyte),
            ("k", ctypes.c_uint32),
        ]

    class SockFprog(ctypes.Structure):
        _fields_ = [
            ("len", ctypes.c_ushort),
            ("filter", ctypes.POINTER(SockFilter)),
        ]

    try:
        libc = ctypes.CDLL(None)
    except Exception:
        return False

    filters = [
        SockFilter(BPF_LD | BPF_W | BPF_ABS, 0, 0, 4),
        SockFilter(BPF_JMP | BPF_JEQ | BPF_K, 1, 0, audit_arch),
        SockFilter(BPF_RET, 0, 0, SECCOMP_RET_ERRNO | EACCES),
        SockFilter(BPF_LD | BPF_W | BPF_ABS, 0, 0, 0),
        SockFilter(BPF_JMP | BPF_JEQ | BPF_K, 0, 1, sys_execve),
        SockFilter(BPF_RET, 0, 0, SECCOMP_RET_ERRNO | EACCES),
        SockFilter(BPF_JMP | BPF_JEQ | BPF_K, 0, 1, sys_ptrace),
        SockFilter(BPF_RET, 0, 0, SECCOMP_RET_ERRNO | EACCES),
        SockFilter(BPF_RET, 0, 0, SECCOMP_RET_ALLOW),
    ]

    filter_array = (SockFilter * len(filters))(*filters)
    program = SockFprog(len(filters), filter_array)

    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0:
        return False

    return (
        not libc.prctl(
            PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(program)
        )
        < 0
    )


def apply_sandbox_to_current_process(
    workspace_path: str | Path, block_execve: bool = False
) -> None:
    """Applies all sandbox constraints to the current process."""
    if platform.system() != "Linux":
        return

    # 1. Namespaces (unshare)
    with contextlib.suppress(Exception):
        libc = ctypes.CDLL(None)
        # Unshare user namespace first to obtain privileges to unshare other namespaces
        libc.unshare(CLONE_NEWUSER)
        # Unshare network (no internet), mount, IPC, and UTS
        libc.unshare(CLONE_NEWNET | CLONE_NEWNS | CLONE_NEWIPC | CLONE_NEWUTS)

    # 2. Resource Limits (setrlimit)
    with contextlib.suppress(Exception):
        # Limit memory (512MB)
        resource.setrlimit(
            resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024)
        )
        # Limit CPU time (30s)
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        # Limit process count (max 10 threads/processes)
        resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
        # Limit file size created (10MB)
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024)
        )

    # 3. Drop capabilities
    with contextlib.suppress(Exception):
        # PR_CAPBSET_DROP is 24
        for cap in range(64):
            libc.prctl(24, cap, 0, 0, 0)

    # 4. Landlock LSM
    try:
        from amberclaw.security.landlock import apply_sandbox  # noqa: PLC0415

        apply_sandbox(workspace_path)
    except Exception as e:
        logger.debug("Landlock setup skipped: %s", e)

    # 5. Seccomp (execve, ptrace)
    if block_execve:
        with contextlib.suppress(Exception):
            apply_seccomp_filters()


class CodeSandbox:
    """Secure execution environment for AmberClaw subagents.

    Interfaces with isolated Docker containers or ephemeral local sandboxing.
    """

    def __init__(
        self,
        use_docker: bool = True,
        default_timeout_sec: int = 30,
        workspace: str | Path | None = None,
    ):
        self.use_docker = use_docker
        self.default_timeout_sec = default_timeout_sec
        self.workspace = Path(workspace or Path.cwd()).resolve()
        self._docker_backend = None
        self._cleanup_task = None
        if self.use_docker:
            from amberclaw.terminal.docker import (  # noqa: PLC0415
                DockerTerminalBackend,
            )

            self._docker_backend = DockerTerminalBackend(
                workspace_dir=str(self.workspace)
            )

    async def start(self) -> None:
        """Starts the Docker container sandbox if Docker is enabled."""
        if self.use_docker and self._docker_backend:
            await self._docker_backend.start()

    async def stop(self) -> None:
        """Stops and cleans up the Docker container sandbox."""
        if self.use_docker and self._docker_backend:
            await self._docker_backend.stop()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def execute_python(
        self, code: str, env_vars: dict[str, str] | None = None
    ) -> ExecutionResult:
        """Executes arbitrary Python code in an isolated sandbox."""
        execution_id = uuid.uuid4().hex[:8]
        logger.info(
            "Executing Python code block [%s] in sandbox. length=%d",
            execution_id,
            len(code),
        )

        if self.use_docker and self._docker_backend:
            try:
                result = await self._docker_backend.execute_python(
                    code, timeout=self.default_timeout_sec, env=env_vars
                )
                return ExecutionResult(
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    exit_code=result.get("exit_code", 0),
                    execution_time_ms=result.get("execution_time_ms", 0.0),
                )
            except Exception as e:
                logger.warning(
                    "Docker sandbox failed: %s. Falling back to local secure sandbox.",
                    e,
                )

        # Local Sandboxing Fallback
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            code_file = tmp_path / "user_code.py"
            code_file.write_text(code, encoding="utf-8")

            bootstrap_file = tmp_path / "bootstrap.py"
            # Set up PYTHONPATH for amberclaw imports
            parent_dir = Path(__file__).parent.parent.parent.resolve()

            bootstrap_code = f"""
import sys
import os

sys.path.insert(0, {str(parent_dir)!r})

from amberclaw.security.sandbox import apply_sandbox_to_current_process

# Initialize sandbox constraints
apply_sandbox_to_current_process({str(self.workspace)!r}, block_execve=True)

# Run the user code
with open({str(code_file)!r}, "r") as f:
    user_code = f.read()

globals_dict = {{
    "__name__": "__main__",
    "__file__": {str(code_file)!r},
}}
exec(user_code, globals_dict)
"""
            bootstrap_file.write_text(bootstrap_code, encoding="utf-8")

            env = dict(env_vars or os.environ)
            env["PYTHONPATH"] = str(parent_dir) + (
                os.pathsep + env.get("PYTHONPATH", "")
                if env.get("PYTHONPATH")
                else ""
            )

            start_time = asyncio.get_event_loop().time()
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    bootstrap_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.default_timeout_sec,
                    )
                    end_time = asyncio.get_event_loop().time()
                    return ExecutionResult(
                        stdout=stdout.decode("utf-8", errors="replace"),
                        stderr=stderr.decode("utf-8", errors="replace"),
                        exit_code=(
                            process.returncode
                            if process.returncode is not None
                            else 0
                        ),
                        execution_time_ms=(end_time - start_time) * 1000,
                    )
                except TimeoutError:
                    try:
                        process.kill()
                        stdout, stderr = await process.communicate()
                    except Exception:
                        stdout, stderr = b"", b""
                    return ExecutionResult(
                        stdout=stdout.decode("utf-8", errors="replace"),
                        stderr=stderr.decode("utf-8", errors="replace")
                        + f"\nTimeout Error: Exceeded {self.default_timeout_sec} seconds.",
                        exit_code=-1,
                        execution_time_ms=self.default_timeout_sec * 1000,
                    )
            except Exception as e:
                logger.error("Local sandbox execution failed: %s", e)
                return ExecutionResult(
                    stdout="", stderr=str(e), exit_code=1, execution_time_ms=0.0
                )

    async def execute_bash(self, command: str) -> ExecutionResult:
        """Executes a bash command in the sandbox."""
        logger.warning("Executing bash command in sandbox: %s", command)

        if self.use_docker and self._docker_backend:
            try:
                result = await self._docker_backend.execute_bash(
                    command, timeout=self.default_timeout_sec
                )
                return ExecutionResult(
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    exit_code=result.get("exit_code", 0),
                    execution_time_ms=result.get("execution_time_ms", 0.0),
                )
            except Exception as e:
                logger.warning(
                    "Docker sandbox failed: %s. Falling back to local secure sandbox.",
                    e,
                )

        # Local Sandboxing Fallback (preexec_fn sandboxing)
        def _preexec():
            apply_sandbox_to_current_process(self.workspace, block_execve=False)

        start_time = asyncio.get_event_loop().time()
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=_preexec,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.default_timeout_sec,
                )
                end_time = asyncio.get_event_loop().time()
                return ExecutionResult(
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    exit_code=(
                        process.returncode
                        if process.returncode is not None
                        else 0
                    ),
                    execution_time_ms=(end_time - start_time) * 1000,
                )
            except TimeoutError:
                try:
                    process.kill()
                    stdout, stderr = await process.communicate()
                except Exception:
                    stdout, stderr = b"", b""
                return ExecutionResult(
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace")
                    + f"\nTimeout Error: Exceeded {self.default_timeout_sec} seconds.",
                    exit_code=-1,
                    execution_time_ms=self.default_timeout_sec * 1000,
                )
        except Exception as e:
            logger.error("Local sandbox bash execution failed: %s", e)
            return ExecutionResult(
                stdout="", stderr=str(e), exit_code=1, execution_time_ms=0.0
            )

    def __del__(self) -> None:
        if self.use_docker and self._docker_backend:
            with contextlib.suppress(Exception):
                # Synchronous cleanup during GC
                if self._docker_backend.container_running:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        self._cleanup_task = loop.create_task(
                            self._docker_backend.stop()
                        )
                    else:
                        loop.run_until_complete(self._docker_backend.stop())
