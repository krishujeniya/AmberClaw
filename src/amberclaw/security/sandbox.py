from __future__ import annotations

import asyncio
import contextlib
import ctypes
import io
import ipaddress
import logging
import os
import platform
import resource
import shutil
import socket
import stat
import sys
import tarfile
import tempfile
import urllib.parse
import uuid
import zipfile
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
SECCOMP_RET_ALLOW = 0x7FFF0000
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
        not libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(program)) < 0
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
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        # Limit CPU time (30s)
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        # Limit process count (max 10 threads/processes)
        resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
        # Limit file size created (10MB)
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))

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
                os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else ""
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
                            process.returncode if process.returncode is not None else 0
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
                        process.returncode if process.returncode is not None else 0
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


class DecompressionSecurityError(PermissionError):
    """Raised when an archive violates decompression limits or attempts path traversal."""


class DecompressionGuard:
    """Guards against archive bombs (zip/tar bombs), zip-slip attacks, and malicious symlinks."""

    DEFAULT_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB
    DEFAULT_MAX_FILES = 1000
    DEFAULT_MAX_RATIO = 100.0  # 100:1 compression ratio limit

    @classmethod
    def extract_zip(
        cls,
        source: str | Path | bytes | io.BytesIO,
        target_dir: str | Path,
        max_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
        max_files: int = DEFAULT_MAX_FILES,
        max_ratio: float = DEFAULT_MAX_RATIO,
    ) -> list[Path]:
        """Safely extracts a ZIP archive preventing zip-slip, symlink attacks, and zip bombs."""
        dest = Path(target_dir).resolve()
        dest.mkdir(parents=True, exist_ok=True)

        if isinstance(source, (str, Path)):
            archive_stream: io.BytesIO | Path = Path(source).resolve()
        elif isinstance(source, bytes):
            archive_stream = io.BytesIO(source)
        else:
            archive_stream = source

        extracted_paths: list[Path] = []
        total_uncompressed = 0
        total_compressed = 0

        with zipfile.ZipFile(archive_stream, "r") as zf:
            infolist = zf.infolist()
            if len(infolist) > max_files:
                raise DecompressionSecurityError(
                    f"ZIP archive contains {len(infolist)} files, exceeding limit of {max_files}"
                )

            for info in infolist:
                # 1. Zip bomb ratio and size checks
                total_uncompressed += info.file_size
                total_compressed += max(info.compress_size, 1)

                if total_uncompressed > max_bytes:
                    raise DecompressionSecurityError(
                        f"Decompressed size exceeds limit of {max_bytes} bytes"
                    )

                ratio = total_uncompressed / total_compressed
                if total_uncompressed > 1024 * 1024 and ratio > max_ratio:
                    raise DecompressionSecurityError(
                        f"Compression ratio {ratio:.1f}:1 exceeds maximum permitted ratio {max_ratio}:1 (Zip bomb detected)"
                    )

                # 2. Zip-Slip Directory Traversal Check
                target_path = (dest / info.filename).resolve()
                if dest not in target_path.parents and target_path != dest:
                    raise DecompressionSecurityError(
                        f"Zip-slip directory traversal attempt detected: {info.filename}"
                    )

                # 3. Check for symlink attacks
                # Unix permissions are in high 16 bits of external_attr
                is_symlink = stat.S_ISLNK(info.external_attr >> 16)
                if is_symlink:
                    raise DecompressionSecurityError(
                        f"Symlinks inside archives are prohibited for safety: {info.filename}"
                    )

                if info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src_file, target_path.open("wb") as out_file:
                        shutil.copyfileobj(src_file, out_file)
                    extracted_paths.append(target_path)

        return extracted_paths

    @classmethod
    @contextlib.contextmanager
    def _open_tar(cls, source: str | Path | bytes | io.BytesIO):
        if isinstance(source, (str, Path)):
            with tarfile.open(str(source), "r:*") as tf:
                yield tf
        elif isinstance(source, bytes):
            with tarfile.open(fileobj=io.BytesIO(source), mode="r:*") as tf:
                yield tf
        else:
            with tarfile.open(fileobj=source, mode="r:*") as tf:
                yield tf

    @classmethod
    def extract_tar(
        cls,
        source: str | Path | bytes | io.BytesIO,
        target_dir: str | Path,
        max_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
        max_files: int = DEFAULT_MAX_FILES,
    ) -> list[Path]:
        """Safely extracts a TAR archive preventing directory traversal and symlink escapes."""
        dest = Path(target_dir).resolve()
        dest.mkdir(parents=True, exist_ok=True)

        extracted_paths: list[Path] = []
        total_uncompressed = 0
        file_count = 0

        with cls._open_tar(source) as tf:
            for member in tf.getmembers():
                file_count += 1
                if file_count > max_files:
                    raise DecompressionSecurityError(
                        f"TAR archive contains > {max_files} files"
                    )

                total_uncompressed += member.size
                if total_uncompressed > max_bytes:
                    raise DecompressionSecurityError(
                        f"Decompressed TAR size exceeds limit of {max_bytes} bytes"
                    )

                # Path traversal check
                target_path = (dest / member.name).resolve()
                if dest not in target_path.parents and target_path != dest:
                    raise DecompressionSecurityError(
                        f"Tar-slip directory traversal attempt detected: {member.name}"
                    )

                # Symlink / Hardlink check
                if member.issym() or member.islnk():
                    raise DecompressionSecurityError(
                        f"Symlinks and hardlinks inside archives are prohibited: {member.name}"
                    )

                if member.isdir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    extracted_file = tf.extractfile(member)
                    if extracted_file is not None:
                        with extracted_file, target_path.open("wb") as out_f:
                            shutil.copyfileobj(extracted_file, out_f)
                    extracted_paths.append(target_path)

        return extracted_paths


class HostSocketAndMetadataFilter:
    """Filters host sockets, loopback/private IP ranges, and cloud metadata endpoints."""

    FORBIDDEN_CIDRS = (
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local & cloud metadata
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("224.0.0.0/4"),  # Multicast
        ipaddress.ip_network("240.0.0.0/4"),  # Reserved
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fe80::/10"),  # IPv6 Link-local
        ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local
    )

    FORBIDDEN_HOSTNAMES = frozenset(
        {
            "instance-data",
            "metadata.google.internal",
            "metadata",
            "169.254.169.254",
            "169.254.170.2",
        }
    )

    FORBIDDEN_SOCKET_NAMES = (
        "docker.sock",
        "containerd.sock",
        "dockershim.sock",
        "crio.sock",
        "podman.sock",
    )

    @classmethod
    def is_forbidden_ip(cls, ip_str: str) -> bool:
        """Returns True if the given IP belongs to private, loopback, or metadata CIDRs."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            return any(ip_obj in cidr for cidr in cls.FORBIDDEN_CIDRS)
        except ValueError:
            return True

    @classmethod
    def verify_destination_host(cls, hostname_or_ip: str) -> bool:
        """Resolves DNS and verifies all resolved IP addresses are public and safe."""
        cleaned = hostname_or_ip.strip().lower()
        if cleaned in cls.FORBIDDEN_HOSTNAMES:
            return False

        try:
            addr_info = socket.getaddrinfo(cleaned, None)
            if not addr_info:
                return False
            for entry in addr_info:
                sockaddr = entry[4]
                ip_cand = sockaddr[0]
                if cls.is_forbidden_ip(ip_cand):
                    logger.warning(
                        "Blocked host [%s] resolved to forbidden address [%s]",
                        cleaned,
                        ip_cand,
                    )
                    return False
            return True
        except socket.gaierror:
            return False

    @classmethod
    def verify_redirect_url(cls, url: str) -> str:
        """Validates redirect URL scheme and verifies destination IP is safe from SSRF."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise PermissionError(f"Prohibited redirect scheme: {parsed.scheme}")

        host = parsed.hostname
        if not host:
            raise PermissionError("Redirect URL missing hostname")

        if not cls.verify_destination_host(host):
            raise PermissionError(
                f"Prohibited SSRF destination: host '{host}' resolves to private/metadata IP"
            )

        return url

    @classmethod
    def is_host_socket_path(cls, path: str | Path) -> bool:
        """Detects whether a path references a host container/orchestrator socket."""
        p_str = str(path).lower()
        return any(sock_name in p_str for sock_name in cls.FORBIDDEN_SOCKET_NAMES)


class EphemeralFilesystemSandbox:
    """Isolated, ephemeral filesystem workspace with strict access containment."""

    def __init__(self, prefix: str = "amberclaw_ephemeral_") -> None:
        self.prefix = prefix
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.path: Path | None = None

    def __enter__(self) -> EphemeralFilesystemSandbox:
        self._temp_dir = tempfile.TemporaryDirectory(prefix=self.prefix)
        self.path = Path(self._temp_dir.name).resolve()
        # Set directory permissions to owner only (0o700)
        with contextlib.suppress(Exception):
            self.path.chmod(0o700)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._temp_dir is not None:
            with contextlib.suppress(Exception):
                self._temp_dir.cleanup()
            self._temp_dir = None
            self.path = None

    def resolve_safe_path(self, relative_path: str | Path) -> Path:
        """Resolves a relative path strictly within the ephemeral sandbox boundary."""
        if self.path is None:
            raise RuntimeError("Ephemeral sandbox is not initialized")

        resolved = (self.path / relative_path).resolve()
        if self.path not in resolved.parents and resolved != self.path:
            raise PermissionError(
                f"Path traversal detected: {relative_path} attempts to escape ephemeral sandbox"
            )
        return resolved


class SandboxEscapeTestRunner:
    """Automated continuous suite verifying sandbox containment and escape resilience."""

    def __init__(self, sandbox: CodeSandbox | None = None) -> None:
        self.sandbox = sandbox or CodeSandbox(use_docker=False)

    async def run_all_checks(self) -> dict[str, bool]:
        """Runs security escape probes and returns test pass/fail results."""
        results: dict[str, bool] = {}

        # 1. Test filesystem containment (attempt to read /etc/shadow)
        res_fs = await self.sandbox.execute_python(
            "import os\n"
            "try:\n"
            "    with open('/etc/shadow', 'r') as f:\n"
            "        data = f.read()\n"
            "    print('FAIL: Read /etc/shadow')\n"
            "except Exception:\n"
            "    print('PASS: Shadow read blocked')\n"
        )
        results["filesystem_containment"] = "PASS" in res_fs.stdout

        # 2. Test host socket access
        results["host_socket_blocked"] = (
            HostSocketAndMetadataFilter.is_host_socket_path("/var/run/docker.sock")
        )

        # 3. Test cloud metadata blocking
        results[
            "cloud_metadata_blocked"
        ] = not HostSocketAndMetadataFilter.verify_destination_host("169.254.169.254")

        # 4. Test private loopback blocking
        results[
            "private_ip_blocked"
        ] = not HostSocketAndMetadataFilter.verify_destination_host("127.0.0.1")

        return results
