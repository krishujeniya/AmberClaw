"""Egress firewall controller for AmberClaw.

Intercepts lower-level socket connections and DNS resolution queries to enforce
egress policy limits.
"""

import contextvars
import ipaddress
import socket
from collections.abc import Generator
from contextlib import contextmanager

from loguru import logger

from amberclaw.security.network_policy import NetworkPolicy

# Context variables to track egress sandboxing rules task-locally
_egress_policy: contextvars.ContextVar[NetworkPolicy | None] = (
    contextvars.ContextVar("egress_policy", default=None)
)
_egress_active: contextvars.ContextVar[bool] = (
    contextvars.ContextVar("egress_active", default=False)
)
_active_binary_context: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar("active_binary_context", default=None)
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


def patched_getaddrinfo(
    host: str, port: str | int | None, *args, **kwargs,
) -> list[tuple]:
    """Intercept and filter name resolution requests."""
    if _egress_active.get():
        policy = _egress_policy.get()
        if policy:
            p = 80
            if port is not None:
                try:
                    p = int(port)
                except ValueError:
                    if port == "https":
                        p = HTTPS_PORT
                    elif port == "http":
                        p = 80

            # Enforce TLS-only endpoints
            if policy.enforce_tls_only and p != HTTPS_PORT:
                logger.warning(
                    "🚫 [Egress Blocked]: Connection port '{}' rejected "
                    "(TLS-only is enforced).",
                    p,
                )
                raise NetworkAccessDenied(
                    f"Egress block: TLS-only is enforced. Port {p} is denied.",
                )

            binary = auto_detect_binary_context()

            if not policy.is_allowed(host, p, binary):
                logger.warning(
                    "🚫 [Egress Blocked]: DNS resolution for '{}:{}' "
                    "denied by network policy (context: {}).",
                    host,
                    port,
                    binary,
                )
                raise NetworkAccessDenied(
                    f"Egress block: Access to {host}:{p} is denied by policy.",
                )

            # SSRF validation: Resolve host first and verify if any IP is private
            results = _original_getaddrinfo(host, port, *args, **kwargs)
            for res in results:
                sockaddr = res[4]
                if sockaddr and len(sockaddr) >= 1:
                    ip_candidate = sockaddr[0]
                    if is_private_ip(ip_candidate):
                        logger.warning(
                            "🚫 [SSRF Guard Blocked]: Host '{}' resolved to private IP '{}'.",
                            host,
                            ip_candidate,
                        )
                        raise NetworkAccessDenied(
                            f"Egress block: SSRF threat detected. Connection to private IP {ip_candidate} is denied.",
                        )
            return results

    return _original_getaddrinfo(host, port, *args, **kwargs)


_MIN_ADDR_LEN = 2


def patched_connect(self: socket.socket, address: tuple) -> None:
    """Intercept and filter direct connection attempts."""
    if _egress_active.get():
        policy = _egress_policy.get()
        if policy and len(address) >= _MIN_ADDR_LEN:
            host, port = address[0], address[1]

            # Direct IP SSRF check
            if is_private_ip(host):
                logger.warning(
                    "🚫 [SSRF Guard Blocked]: Direct connection to private range '{}' denied.",
                    host,
                )
                raise NetworkAccessDenied(
                    f"Egress block: SSRF threat detected. Direct connection to private IP {host} is denied.",
                )

            # TLS-only check
            if policy.enforce_tls_only and port != HTTPS_PORT:
                logger.warning(
                    "🚫 [Egress Blocked]: Direct connection to port '{}' rejected "
                    "(TLS-only is enforced).",
                    port,
                )
                raise NetworkAccessDenied(
                    f"Egress block: TLS-only is enforced. Port {port} is denied.",
                )

            binary = auto_detect_binary_context()

            if not policy.is_allowed(host, port, binary):
                logger.warning(
                    "🚫 [Egress Blocked]: Connection to '{}:{}' "
                    "denied by network policy (context: {}).",
                    host,
                    port,
                    binary,
                )
                raise NetworkAccessDenied(
                    f"Egress block: Connection to {host}:{port} is denied.",
                )

    return _original_connect(self, address)


def patched_connect_ex(self: socket.socket, address: tuple) -> int:
    """Intercept and filter connect_ex connections."""
    if _egress_active.get():
        try:
            patched_connect(self, address)
            return 0
        except NetworkAccessDenied as e:
            raise e
    return _original_connect_ex(self, address)


class _PatchState:
    is_patched = False


def apply_egress_patches() -> None:
    """Apply global monkeypatches once safely."""
    if not _PatchState.is_patched:
        socket.getaddrinfo = patched_getaddrinfo
        socket.socket.connect = patched_connect
        socket.socket.connect_ex = patched_connect_ex
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
