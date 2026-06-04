"""Role-Based Access Control (RBAC) security manager."""

import contextlib
import contextvars
from collections.abc import Generator

from loguru import logger

# Context variable to propagate the current message sender ID
_current_sender_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_sender_id", default=None
)


class RBACPermissionDenied(PermissionError):
    """Exception raised when a user is not permitted to execute a tool."""

    def __init__(self, sender_id: str | None, role: str, tool_name: str):
        super().__init__(
            f"Permission Denied: User '{sender_id}' with role '{role}' is not allowed to execute tool '{tool_name}'"
        )
        self.sender_id = sender_id
        self.role = role
        self.tool_name = tool_name


@contextlib.contextmanager
def active_sender_context(sender_id: str | None) -> Generator[None, None, None]:
    """Context manager to set the active sender ID in context variables."""
    token = _current_sender_id.set(sender_id)
    try:
        yield
    finally:
        _current_sender_id.reset(token)


def check_tool_permission(tool_name: str) -> None:
    """
    Check if the current sender has permission to execute the specified tool.

    Raises RBACPermissionDenied if unauthorized.
    """
    from amberclaw.config.schema import settings

    if not settings.security.rbac.enabled:
        return

    sender_id = _current_sender_id.get()

    # System and CLI operations bypass RBAC checks (sender_id is None, "system", "user")
    if sender_id is None or sender_id in ("system", "user"):
        logger.debug("RBAC check bypassed for system/CLI context")
        return

    rbac_cfg = settings.security.rbac
    role = rbac_cfg.user_roles.get(sender_id, rbac_cfg.default_role)
    allowed_tools = rbac_cfg.role_permissions.get(role, [])

    # If allowed tools has "*", all tools are permitted
    if "*" in allowed_tools or tool_name in allowed_tools:
        logger.debug(
            "User '{}' with role '{}' is authorized to execute '{}'",
            sender_id,
            role,
            tool_name,
        )
        return

    logger.warning(
        "User '{}' with role '{}' blocked from executing tool '{}'",
        sender_id,
        role,
        tool_name,
    )
    raise RBACPermissionDenied(sender_id, role, tool_name)
