# ruff: noqa: PLR2004
"""Unit tests for CL-026: Extension Contract Conformance, Lifecycle, and Governance."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from amberclaw.plugins.capabilities import PluginCapability
from amberclaw.plugins.registry import PluginManifest, PluginRegistry
from amberclaw.security.approval import ApprovalStatus, ToolApprovalManager, ToolRiskLevel


def test_extension_manifest_parsing_and_capability_validation(tmp_path):
    """Verify plugin.yaml parsing, capability boundaries, and version constraints."""
    ext_dir = tmp_path / "custom_jira_sync"
    ext_dir.mkdir()

    manifest_content = """
name: custom_jira_sync
version: 1.2.0
description: "Syncs assigned tickets to local SQLite queue"
entrypoint: main.py
capabilities:
  - filesystem_read
  - network_access
"""
    (ext_dir / "plugin.yaml").write_text(manifest_content, encoding="utf-8")
    (ext_dir / "main.py").write_text("# entrypoint\n", encoding="utf-8")

    registry = PluginRegistry(tmp_path)
    plugins = registry.discover_plugins()

    assert "custom_jira_sync" in plugins
    manifest = plugins["custom_jira_sync"]
    assert manifest.name == "custom_jira_sync"
    assert manifest.version == "1.2.0"
    assert PluginCapability.FILESYSTEM_READ in manifest.capabilities
    assert PluginCapability.NETWORK_ACCESS in manifest.capabilities
    assert PluginCapability.FILESYSTEM_WRITE not in manifest.capabilities


def test_extension_lifecycle_install_update_revoke(tmp_path):
    """Verify install, update, and revocation lifecycle for extensions."""
    repo_dir = tmp_path / "active_extensions"
    repo_dir.mkdir()

    registry = PluginRegistry(repo_dir)

    # 1. Install extension v1.0.0
    ext_dir = repo_dir / "audit_tool"
    ext_dir.mkdir()
    (ext_dir / "plugin.yaml").write_text(
        "name: audit_tool\nversion: 1.0.0\nentrypoint: main.py\ncapabilities: []\n",
        encoding="utf-8",
    )
    (ext_dir / "main.py").write_text("# v1.0.0\n", encoding="utf-8")

    manifests = registry.discover_plugins()
    assert "audit_tool" in manifests
    assert manifests["audit_tool"].version == "1.0.0"

    # 2. Update extension to v1.1.0
    (ext_dir / "plugin.yaml").write_text(
        "name: audit_tool\nversion: 1.1.0\nentrypoint: main.py\ncapabilities: []\n",
        encoding="utf-8",
    )
    manifests_updated = registry.discover_plugins()
    assert manifests_updated["audit_tool"].version == "1.1.0"

    # 3. Revoke extension (remove or disable)
    (ext_dir / "plugin.yaml").unlink()
    manifests_revoked = registry.discover_plugins()
    assert "audit_tool" not in manifests_revoked


def test_unreviewed_automatic_tool_execution_denied_for_extensions():
    """Verify extensions cannot execute mutating tools without explicit human approval."""
    approval_mgr = ToolApprovalManager.get_instance()
    approval_mgr._tickets.clear()

    # Third-party plugin attempts privileged mutation
    decision = approval_mgr.evaluate_tool_execution(
        tool_name="jira_delete_ticket",
        agent_id="plugin_jira_sync",
        args={"issue_key": "PROJ-102"},
        risk_level=ToolRiskLevel.HIGH,
        tenant_id="default",
    )

    # Must NOT be automatically approved
    assert decision.status == ApprovalStatus.PENDING_APPROVAL
    assert decision.ticket is not None
    assert decision.ticket.tool_name == "jira_delete_ticket"
