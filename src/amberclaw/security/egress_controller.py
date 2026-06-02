"""Egress firewall controller for AmberClaw.

Intercepts lower-level socket connections and DNS resolution queries to enforce
egress policy limits.
"""

import contextvars
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

# Store original socket methods
_original_getaddrinfo = socket.getaddrinfo
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex


class NetworkAccessDeniedError(PermissionError):
    """Exception raised when an agent tries to contact an unauthorized host/port."""

    pass


NetworkAccessDenied = NetworkAccessDeniedError


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
                        p = 443
                    elif port == "http":
                        p = 80

            if not policy.is_allowed(host, p):
                logger.warning(
                    "🚫 [Egress Blocked]: DNS resolution for '{}:{}' "
                    "denied by network policy.",
                    host,
                    port,
                )
                raise NetworkAccessDenied(
                    f"Egress block: Access to {host}:{p} is denied by policy.",
                )

    return _original_getaddrinfo(host, port, *args, **kwargs)


_MIN_ADDR_LEN = 2


def patched_connect(self: socket.socket, address: tuple) -> None:
    """Intercept and filter direct connection attempts."""
    if _egress_active.get():
        policy = _egress_policy.get()
        if policy and len(address) >= _MIN_ADDR_LEN:
            host, port = address[0], address[1]
            if not policy.is_allowed(host, port):
                logger.warning(
                    "🚫 [Egress Blocked]: Connection to '{}:{}' "
                    "denied by network policy.",
                    host,
                    port,
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
