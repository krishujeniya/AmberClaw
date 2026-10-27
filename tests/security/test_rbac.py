import pytest
from unittest.mock import patch, MagicMock

from amberclaw.security.auth import (
    check_tool_permission,
    check_object_permission,
    active_sender_context,
    RBACPermissionDenied,
    ObjectPermissionDenied,
)


@pytest.fixture
def mock_rbac_settings():
    with patch("amberclaw.config.schema.settings") as mock_settings:
        mock_settings.security.rbac.enabled = True
        mock_settings.security.rbac.default_role = "user"
        mock_settings.security.rbac.user_roles = {
            "admin_usr": "admin",
            "guest_usr": "guest",
            "operator_usr": "operator",
        }
        mock_settings.security.rbac.role_permissions = {
            "admin": ["*"],
            "operator": ["read_file", "search_web"],
            "guest": ["read_file"],
            "user": ["read_file"],
        }
        yield mock_settings


def test_system_and_cli_bypass_rbac(mock_rbac_settings):
    # System and None contexts should bypass RBAC checks
    with active_sender_context(None):
        check_tool_permission("dangerous_tool")

    with active_sender_context("system"):
        check_tool_permission("dangerous_tool")

    with active_sender_context("user"):
        check_tool_permission("dangerous_tool")


def test_rbac_authorized_tool_execution(mock_rbac_settings):
    with active_sender_context("operator_usr"):
        check_tool_permission("read_file")
        check_tool_permission("search_web")


def test_rbac_blocked_tool_execution(mock_rbac_settings):
    with active_sender_context("operator_usr"):
        with pytest.raises(RBACPermissionDenied) as exc_info:
            check_tool_permission("execute_bash")
        assert exc_info.value.tool_name == "execute_bash"
        assert exc_info.value.role == "operator"


def test_privilege_escalation_blocked(mock_rbac_settings):
    # Guest user attempting to invoke administrative tools
    with active_sender_context("guest_usr"):
        with pytest.raises(RBACPermissionDenied):
            check_tool_permission("admin_config")

        with pytest.raises(RBACPermissionDenied):
            check_tool_permission("execute_bash")


def test_object_level_authorization_owner(mock_rbac_settings):
    # Resource owner accessing own resource succeeds
    with active_sender_context("operator_usr"):
        check_object_permission(resource_owner_id="operator_usr", action="read")


def test_object_level_authorization_cross_tenant_denied(mock_rbac_settings):
    # Operator user accessing guest user's resource is denied
    with active_sender_context("operator_usr"):
        with pytest.raises(ObjectPermissionDenied) as exc_info:
            check_object_permission(resource_owner_id="guest_usr", action="read")
        assert exc_info.value.sender_id == "operator_usr"
        assert exc_info.value.resource_owner_id == "guest_usr"


def test_object_level_authorization_admin_override(mock_rbac_settings):
    # Admin user accessing another user's resource succeeds
    with active_sender_context("admin_usr"):
        check_object_permission(resource_owner_id="guest_usr", action="read")
