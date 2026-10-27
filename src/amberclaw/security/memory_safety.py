"""Memory zeroing and volatile secret management for sensitive material.

Ensures that encryption keys, authentication tokens, and passwords
are securely overwritten with zeros in memory when no longer needed.
"""

from __future__ import annotations

import ctypes
import hmac
import logging
from types import TracebackType
from typing import Any

logger = logging.getLogger(__name__)


def zero_memory(target: bytearray | memoryview | ctypes.Array[Any] | None) -> None:
    """Securely overwrites a mutable memory buffer with zeros using memset.

    Prevents key leakage in process core dumps, swap files, or memory inspection.
    """
    if target is None:
        return

    try:
        if isinstance(target, bytearray):
            length = len(target)
            if length > 0:
                char_array = (ctypes.c_char * length).from_buffer(target)
                ctypes.memset(ctypes.byref(char_array), 0, length)
        elif isinstance(target, memoryview):
            length = len(target)
            if length > 0 and not target.readonly:
                char_array = (ctypes.c_char * length).from_buffer(target)
                ctypes.memset(ctypes.byref(char_array), 0, length)
        elif hasattr(target, "_type_") and hasattr(target, "_length_"):
            ctypes.memset(ctypes.byref(target), 0, ctypes.sizeof(target))
    except Exception as e:
        logger.debug("Memory zeroing fallback encountered: %s", e)
        # Fallback to manual overwrite if ctypes buffer mapping is restricted
        if isinstance(target, bytearray):
            for i in range(len(target)):
                target[i] = 0


class SecureSecret:
    """Ephemeral container holding sensitive credential material in a zeroable buffer.

    Supports context management for deterministic wiping upon scope exit.
    """

    def __init__(self, secret: str | bytes | bytearray) -> None:
        if isinstance(secret, str):
            raw = secret.encode("utf-8")
        elif isinstance(secret, (bytes, bytearray)):
            raw = bytes(secret)
        else:
            raise TypeError(f"Unsupported secret type: {type(secret)}")

        self._buffer: bytearray | None = bytearray(raw)
        self._length = len(raw)
        self._is_wiped = False

    @property
    def is_wiped(self) -> bool:
        """Whether the buffer has already been zeroed."""
        return self._is_wiped

    def get_bytes(self) -> bytes:
        """Returns the raw bytes of the secret if not yet wiped."""
        if self._is_wiped or self._buffer is None:
            raise ValueError("Attempted to access wiped SecureSecret")
        return bytes(self._buffer)

    def get_str(self, encoding: str = "utf-8") -> str:
        """Decodes the secret into a string if not yet wiped."""
        return self.get_bytes().decode(encoding)

    def compare(self, other: str | bytes | SecureSecret) -> bool:
        """Performs a constant-time comparison to prevent timing attacks."""
        if self._is_wiped or self._buffer is None:
            return False

        if isinstance(other, SecureSecret):
            if other.is_wiped or other._buffer is None:
                return False
            return hmac.compare_digest(self._buffer, other._buffer)

        if isinstance(other, str):
            return hmac.compare_digest(self._buffer, other.encode("utf-8"))

        if isinstance(other, (bytes, bytearray)):
            return hmac.compare_digest(self._buffer, other)

        return False

    def wipe(self) -> None:
        """Wipes the underlying memory buffer by overwriting it with zeros."""
        if not self._is_wiped and self._buffer is not None:
            zero_memory(self._buffer)
            self._buffer = None
            self._is_wiped = True

    def __enter__(self) -> SecureSecret:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.wipe()

    def __del__(self) -> None:
        self.wipe()

    def __repr__(self) -> str:
        status = "wiped" if self._is_wiped else "active"
        return f"<SecureSecret status={status} length={self._length}>"

    def __str__(self) -> str:
        return "[REDACTED_SECURE_SECRET]"
