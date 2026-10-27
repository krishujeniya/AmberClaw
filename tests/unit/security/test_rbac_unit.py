"""Unit tests for the Role-Based Access Control (RBAC) security system."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from amberclaw.agent.tools.base import PydanticTool
from amberclaw.agent.tools.registry import ToolRegistry
from amberclaw.security.auth import (
    RBACPermissionDenied,
    active_sender_context,
    check_tool_permission,
)


class _DummyArgs(BaseModel):
    dummy_arg: str


class _DummyTool(PydanticTool):
    name = "test_tool"
    description = "A dummy tool for testing permissions"
    args_schema = _DummyArgs

    async def run(self, args: _DummyArgs) -> str:
        return f"success: {args.dummy_arg}"


@pytest.fixture
def mock_settings():
    """Fixture to easily mock settings."""
    with patch("amberclaw.config.schema.settings") as mock:
        # Default config
        mock.security = SimpleNamespace(
            rbac=SimpleNamespace(
                enabled=True,
                user_roles={
                    "admin_user": "admin",
                    "regular_user": "user",
                    "guest_user": "guest",
                },
                role_permissions={
                    "admin": ["*"],
                    "user": ["test_tool", "message"],
                    "guest": ["message"],
                },
                default_role="guest",
            )
        )
        yield mock


def test_rbac_disabled(mock_settings):
    """When RBAC is disabled, any user should be allowed to run any tool."""
    mock_settings.security.rbac.enabled = False

    with active_sender_context("guest_user"):
        # Should not raise any error
        check_tool_permission("test_tool")


def test_rbac_system_cli_bypass(mock_settings):
    """System, user, and None sender IDs should bypass RBAC checks."""
    assert mock_settings is not None
    for system_sender in (None, "system", "user"):
        with active_sender_context(system_sender):
            check_tool_permission("restricted_tool")


def test_rbac_admin_full_access(mock_settings):
    """Admin users with '*' permission should have full tool access."""
    assert mock_settings is not None
    with active_sender_context("admin_user"):
        check_tool_permission("any_tool_whatsoever")


def test_rbac_authorized_tool(mock_settings):
    """Regular users should be allowed to run authorized tools."""
    assert mock_settings is not None
    with active_sender_context("regular_user"):
        # test_tool is authorized for 'user'
        check_tool_permission("test_tool")


def test_rbac_unauthorized_tool(mock_settings):
    """Users running unauthorized tools should raise RBACPermissionDenied."""
    assert mock_settings is not None
    with active_sender_context("regular_user"):
        # unauthorized_tool is not authorized for 'user'
        with pytest.raises(RBACPermissionDenied) as exc_info:
            check_tool_permission("unauthorized_tool")

        assert exc_info.value.sender_id == "regular_user"
        assert exc_info.value.role == "user"
        assert exc_info.value.tool_name == "unauthorized_tool"


def test_rbac_default_role_fallback(mock_settings):
    """Unknown users should fall back to default_role permissions."""
    assert mock_settings is not None
    # unknown_user is not in user_roles, should fallback to guest (which only has 'message')
    with active_sender_context("unknown_user"):
        # Should allow 'message'
        check_tool_permission("message")

        # Should block 'test_tool'
        with pytest.raises(RBACPermissionDenied) as exc_info:
            check_tool_permission("test_tool")

        assert exc_info.value.role == "guest"


@pytest.mark.asyncio
async def test_tool_registry_rbac_enforcement(mock_settings):
    """ToolRegistry.execute should enforce RBAC and return formatted error messages."""
    assert mock_settings is not None
    registry = ToolRegistry()
    tool = _DummyTool()
    registry.register(tool)

    # 1. Bypassed / Allowed
    with active_sender_context("regular_user"):
        res = await registry.execute("test_tool", {"dummy_arg": "hello"})
        assert "success: hello" in res

    # 2. Blocked
    with active_sender_context("guest_user"):
        res = await registry.execute("test_tool", {"dummy_arg": "hello"})
        assert "Error: Permission Denied" in res
        assert "guest_user" in res
        assert "guest" in res
        assert "test_tool" in res


@pytest.mark.asyncio
async def test_wrapped_langchain_tool_rbac_enforcement(mock_settings):
    """Wrapped langchain tool's _arun should enforce RBAC."""
    assert mock_settings is not None
    tool = _DummyTool()
    lc_tool = tool.to_langchain_tool()

    # 1. Allowed
    with active_sender_context("regular_user"):
        res = await lc_tool._arun(dummy_arg="hello")
        assert "success: hello" in res

    # 2. Blocked
    with active_sender_context("guest_user"):
        res = await lc_tool._arun(dummy_arg="hello")
        assert "Error: Permission Denied" in res
        assert "guest_user" in res
