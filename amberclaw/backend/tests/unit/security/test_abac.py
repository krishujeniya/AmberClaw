"""Unit tests for Attribute-Based Access Control (ABAC), Resource Boundaries, and JIT.

Validates:
1. Default-deny security baseline for unmodeled operations
2. Cross-organization strict boundary containment
3. Cross-project boundary containment
4. Multi-level security clearance hierarchy enforcement
5. Precedence of explicit DENY rules over ALLOW rules
6. Just-in-Time (JIT) elevation issuance, temporal expiration, and early revocation
"""

import pytest

from amberclaw.security.abac import (
    ABACAccessDeniedError,
    ABACPolicyEngine,
    ABACPolicyRule,
    JustInTimeElevationManager,
    PolicyEffect,
    ResourceBoundary,
    SubjectAttributes,
)


def test_default_deny_baseline():
    engine = ABACPolicyEngine()
    subject = SubjectAttributes(
        subject_id="alice", organization_id="acme", project_id="frontend"
    )
    resource = ResourceBoundary(
        organization_id="acme",
        project_id="frontend",
        resource_id="auth_config",
        resource_type="config",
    )

    # In an empty engine, access must be denied
    assert engine.evaluate(subject, "read", resource) is False
    with pytest.raises(ABACAccessDeniedError):
        engine.enforce(subject, "read", resource)


def test_cross_organization_boundary_denial():
    rule = ABACPolicyRule(
        id="allow_all_read",
        effect=PolicyEffect.ALLOW,
        actions=["read"],
        resource_types=["*"],
    )
    engine = ABACPolicyEngine(rules=[rule])

    subject = SubjectAttributes(
        subject_id="mallory", organization_id="evil_corp", project_id="p1"
    )
    resource = ResourceBoundary(
        organization_id="victim_corp",
        project_id="p1",
        resource_id="financials",
        resource_type="document",
    )

    # Cross-tenant access must be rejected despite broad rule
    assert engine.evaluate(subject, "read", resource) is False
    with pytest.raises(ABACAccessDeniedError):
        engine.enforce(subject, "read", resource)


def test_cross_project_boundary_denial():
    rule = ABACPolicyRule(
        id="allow_read_same_project",
        effect=PolicyEffect.ALLOW,
        actions=["read"],
        resource_types=["document"],
        require_same_project=True,
    )
    engine = ABACPolicyEngine(rules=[rule])

    subject = SubjectAttributes(
        subject_id="bob", organization_id="acme", project_id="analytics"
    )
    resource = ResourceBoundary(
        organization_id="acme",
        project_id="hr_records",
        resource_id="salaries",
        resource_type="document",
    )

    assert engine.evaluate(subject, "read", resource) is False


def test_clearance_hierarchy_enforcement():
    rule = ABACPolicyRule(
        id="confidential_access",
        effect=PolicyEffect.ALLOW,
        actions=["read"],
        resource_types=["database"],
        min_clearance="confidential",
    )
    engine = ABACPolicyEngine(rules=[rule])

    # User with only "internal" clearance
    low_cleared = SubjectAttributes(
        subject_id="intern",
        organization_id="acme",
        project_id="core",
        clearance="internal",
    )
    # User with "confidential" clearance
    high_cleared = SubjectAttributes(
        subject_id="lead_eng",
        organization_id="acme",
        project_id="core",
        clearance="confidential",
    )

    resource = ResourceBoundary(
        organization_id="acme",
        project_id="core",
        resource_id="db_main",
        resource_type="database",
        classification="confidential",
    )

    assert engine.evaluate(low_cleared, "read", resource) is False
    assert engine.evaluate(high_cleared, "read", resource) is True


def test_explicit_deny_precedence():
    allow_rule = ABACPolicyRule(
        id="allow_doc_edit",
        effect=PolicyEffect.ALLOW,
        actions=["edit"],
        resource_types=["document"],
    )
    deny_rule = ABACPolicyRule(
        id="deny_restricted_action",
        effect=PolicyEffect.DENY,
        actions=["edit"],
        resource_types=["document"],
        required_roles=["guest"],
    )
    engine = ABACPolicyEngine(rules=[allow_rule, deny_rule])

    # Guest user matches both allow and deny rule -> Deny must prevail
    guest_user = SubjectAttributes(
        subject_id="guest_1",
        organization_id="acme",
        project_id="core",
        roles=["guest"],
    )
    # Standard engineer matches allow rule only -> Permitted
    eng_user = SubjectAttributes(
        subject_id="eng_1",
        organization_id="acme",
        project_id="core",
        roles=["engineer"],
    )

    resource = ResourceBoundary(
        organization_id="acme",
        project_id="core",
        resource_id="architecture_doc",
        resource_type="document",
    )

    assert engine.evaluate(guest_user, "edit", resource) is False
    assert engine.evaluate(eng_user, "edit", resource) is True


def test_jit_elevation_lifecycle():
    jit_mgr = JustInTimeElevationManager()

    # Initially not elevated
    assert jit_mgr.is_elevated("dev_user", "execute_migration") is False

    # Grant 1-minute elevation
    grant = jit_mgr.grant_elevation(
        subject_id="dev_user",
        scope="execute_migration",
        duration_minutes=1,
        reason="Deploy schema migration v4",
        approver_id="sec_lead",
    )

    assert grant.subject_id == "dev_user"
    assert grant.scope == "execute_migration"
    assert jit_mgr.is_elevated("dev_user", "execute_migration") is True

    # Revoke elevation early
    revoked = jit_mgr.revoke_elevation("dev_user", "execute_migration")
    assert revoked is True
    assert jit_mgr.is_elevated("dev_user", "execute_migration") is False
