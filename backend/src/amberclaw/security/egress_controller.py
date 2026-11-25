"""Egress firewall controller for AmberClaw.

Intercepts lower-level socket connections and DNS resolution queries to enforce
egress policy limits.
"""

import contextvars
import ipaddress
import socket
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TypeAlias

from loguru import logger
from typing_extensions import Buffer

from amberclaw.security.network_policy import NetworkPolicy

# Context variables to track egress sandboxing rules task-locally
_egress_policy: contextvars.ContextVar[NetworkPolicy | None] = contextvars.ContextVar(
    "egress_policy", default=None
)
_egress_active: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "egress_active", default=False
)
_active_binary_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "active_binary_context", default=None
)

# Store original socket methods
_original_getaddrinfo = socket.getaddrinfo
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex

HTTPS_PORT = 443


class NetworkAccessDeniedError(PermissionError):
    """Exception raised when an agent tries to contact an unauthorized host/port."""

    pass


NetworkAccessDenied = NetworkAccessDeniedError


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address resides in a private, loopback, or link-local range (SSRF guard)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
    except ValueError:
        return False


@contextmanager
def binary_context(name: str) -> Generator[None, None, None]:
    """Set the active binary context (e.g. 'git', 'pip') for egress filtering."""
    token = _active_binary_context.set(name)
    try:
        yield
    finally:
        _active_binary_context.reset(token)


def auto_detect_binary_context() -> str | None:
    """Detect calling binary from context variable or execution stack trace."""
    ctx = _active_binary_context.get()
    if ctx:
        return ctx

    import inspect  # noqa: PLC0415

    try:
        for frame_info in inspect.stack():
            filename = frame_info.filename.lower()
            if "git" in filename:
                return "git"
            if "pip" in filename or "pypi" in filename:
                return "pip"
            if "playwright" in filename:
                return "playwright"
    except Exception as e:
        logger.debug("Stack inspection for binary context failed: {}", e)
    return None


# Match the stdlib address shapes, then validate the IP-specific subset at runtime.
_SocketAddress: TypeAlias = tuple[object, ...] | str | Buffer
_AddrInfo: TypeAlias = tuple[
    socket.AddressFamily,
    socket.SocketKind,
    int,
    str,
    tuple[str, int] | tuple[str, int, int, int] | tuple[int, bytes],
]


def _policy_host(host: bytes | str | None) -> str:
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError as exc:
            raise NetworkAccessDenied(
                "Egress block: Invalid hostname encoding"
            ) from exc
    if not host:
        raise NetworkAccessDenied("Egress block: A destination hostname is required")
    return host


def _policy_port(port: bytes | str | int | None) -> int:
    if port is None:
        return 80
    try:
        return int(port)
    except ValueError:
        if port in ("https", b"https"):
            return HTTPS_PORT
        if port in ("http", b"http"):
            return 80
        raise NetworkAccessDenied(
            "Egress block: Unsupported destination service"
        ) from None


def _check_policy(host: str, port: int, policy: NetworkPolicy) -> None:
    if policy.enforce_tls_only and port != HTTPS_PORT:
        raise NetworkAccessDenied(
            f"Egress block: TLS-only is enforced. Port {port} is denied."
        )
    if not policy.is_allowed(host, port, auto_detect_binary_context()):
        raise NetworkAccessDenied(
            f"Egress block: Access to {host}:{port} is denied by policy."
        )


def patched_getaddrinfo(  # noqa: PLR0913 - exact stdlib public callback signature
    host: bytes | str | None,
    port: bytes | str | int | None,
    family: int = 0,
    type: int = 0,  # noqa: A002 - stdlib accepts this keyword
    proto: int = 0,
    flags: int = 0,
) -> list[_AddrInfo]:
    """Intercept resolution using the complete stdlib signature."""
    policy = _egress_policy.get() if _egress_active.get() else None
    if policy is not None:
        _check_policy(_policy_host(host), _policy_port(port), policy)
    results = _original_getaddrinfo(host, port, family, type, proto, flags)
    if policy is not None:
        for resolved_family, _, _, _, sockaddr in results:
            ip_candidate = sockaddr[0]
            if resolved_family not in (
                socket.AF_INET,
                socket.AF_INET6,
            ) or not isinstance(ip_candidate, str):
                raise NetworkAccessDenied("Egress block: Unsupported resolved address")
            try:
                ipaddress.ip_address(ip_candidate)
            except ValueError as exc:
                raise NetworkAccessDenied("Egress block: Invalid resolved IP") from exc
            if is_private_ip(ip_candidate):
                raise NetworkAccessDenied(
                    f"Egress block: SSRF threat detected. Connection to private IP {ip_candidate} is denied."
                )
    return results


_MIN_ADDR_LEN = 2


def _check_connection(sock: socket.socket, address: _SocketAddress) -> _SocketAddress:
    policy = _egress_policy.get() if _egress_active.get() else None
    if policy is None:
        return address
    # Egress policy describes internet hosts/ports; local and other address
    # families have no matching policy and must fail closed inside the sandbox.
    if (
        sock.family not in (socket.AF_INET, socket.AF_INET6)
        or not isinstance(address, tuple)
        or len(address) < _MIN_ADDR_LEN
    ):
        raise NetworkAccessDenied("Egress block: Unsupported socket address")
    host, port = address[0], address[1]
    if not isinstance(host, (str, bytes)) or not isinstance(port, int):
        raise NetworkAccessDenied("Egress block: Invalid destination address")
    normalized_host = _policy_host(host)
    if is_private_ip(normalized_host):
        raise NetworkAccessDenied(
            f"Egress block: SSRF threat detected. Direct connection to private IP {normalized_host} is denied."
        )
    _check_policy(normalized_host, port, policy)
    try:
        ipaddress.ip_address(normalized_host)
    except ValueError:
        # C socket.connect resolves names internally, bypassing Python's patched
        # resolver. Resolve and pin the verified address to prevent that bypass
        # and a second DNS lookup changing the destination after inspection.
        resolved = patched_getaddrinfo(
            normalized_host, port, sock.family, sock.type, sock.proto
        )
        if not resolved:
            raise NetworkAccessDenied(
                "Egress block: No resolved destination address"
            ) from None
        return resolved[0][4]
    return address


def patched_connect(self: socket.socket, address: _SocketAddress) -> None:
    """Filter destinations without altering socket.connect behavior."""
    destination = _check_connection(self, address)
    _original_connect(self, destination)


def patched_connect_ex(self: socket.socket, address: _SocketAddress) -> int:
    """Filter destinations and preserve connect_ex's errno return contract."""
    destination = _check_connection(self, address)
    return _original_connect_ex(self, destination)


class _PatchState:
    is_patched = False


def _patch_socket_method(
    name: str, replacement: Callable[[socket.socket, _SocketAddress], int | None]
) -> None:
    """Replace a built-in descriptor at the typed monkeypatch boundary."""
    setattr(socket.socket, name, replacement)


def apply_egress_patches() -> None:
    """Apply global monkeypatches once safely."""
    if not _PatchState.is_patched:
        socket.getaddrinfo = patched_getaddrinfo
        # Runtime replacement of built-in method descriptors is intentional;
        # setattr is the monkeypatch boundary, while wrappers retain stdlib inputs.
        _patch_socket_method("connect", patched_connect)
        _patch_socket_method("connect_ex", patched_connect_ex)
        _PatchState.is_patched = True


@contextmanager
def egress_sandbox(policy: NetworkPolicy) -> Generator[None, None, None]:
    """Enable the egress firewall for this context manager block (task-local)."""
    apply_egress_patches()

    token_active = _egress_active.set(True)
    token_policy = _egress_policy.set(policy)
    try:
        yield
    finally:
        _egress_active.reset(token_active)
        _egress_policy.reset(token_policy)
