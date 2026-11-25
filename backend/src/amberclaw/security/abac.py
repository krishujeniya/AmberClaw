# ruff: noqa: ERA001, S110
"""Attribute-Based Access Control (ABAC), Resource Boundaries, and Just-in-Time Elevation.

Implements:
1. Strict hierarchical resource containment: Organization -> Project -> Workspace -> Agent -> Resource.
2. Default-deny ABAC evaluation engine with cross-tenant and cross-project isolation.
3. Just-in-Time (JIT) elevation for dangerous operations with automatic time-based expiry and audit trail.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class ResourceBoundary(BaseModel):
    """Hierarchical security boundary coordinates for an AmberClaw resource."""

    organization_id: str = Field(default="default_org")
    project_id: str = Field(default="default_project")
    workspace_id: str = Field(default="default_workspace")
    agent_id: str = Field(default="default_agent")
    resource_id: str = Field(...)
    resource_type: str = Field(...)
    classification: str = Field(
        default="internal"
    )  # public, internal, confidential, restricted


class SubjectAttributes(BaseModel):
    """Contextual security attributes describing the requesting user or agent."""

    subject_id: str
    organization_id: str = "default_org"
    project_id: str = "default_project"
    roles: list[str] = Field(default_factory=lambda: ["user"])
    clearance: str = "internal"  # public, internal, confidential, restricted


class ABACAccessDeniedError(PermissionError):
    """Raised when an action is blocked by default-deny ABAC policy or cross-boundary mismatch."""


class ABACPolicyRule(BaseModel):
    """Declarative attribute-based policy statement."""

    id: str
    description: str = ""
    effect: PolicyEffect = PolicyEffect.ALLOW
    actions: list[str] = Field(default_factory=lambda: ["*"])
    resource_types: list[str] = Field(default_factory=lambda: ["*"])
    required_roles: list[str] = Field(default_factory=list)
    min_clearance: str | None = None
    require_same_org: bool = True
    require_same_project: bool = True


CLEARANCE_HIERARCHY = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}


class ABACPolicyEngine:
    """Evaluates access requests under default-deny attribute-based policy semantics."""

    def __init__(self, rules: list[ABACPolicyRule] | None = None) -> None:
        self.rules: list[ABACPolicyRule] = rules or []

    def add_rule(self, rule: ABACPolicyRule) -> None:
        self.rules.append(rule)

    def evaluate(
        self,
        subject: SubjectAttributes,
        action: str,
        resource: ResourceBoundary,
    ) -> bool:
        """Evaluate access request against boundary checks and rules under default-deny."""
        # 1. Fundamental Organization Boundary check
        if subject.organization_id != resource.organization_id:
            logger.warning(
                "Cross-org access denied: Subject org '{}' != Resource org '{}'",
                subject.organization_id,
                resource.organization_id,
            )
            return False

        # 2. Check for explicit DENY rules first
        for rule in self.rules:
            if rule.effect == PolicyEffect.DENY and self._rule_matches(
                rule, subject, action, resource
            ):
                logger.warning(
                    "ABAC rule '{}' explicitly denied access for '{}'",
                    rule.id,
                    subject.subject_id,
                )
                return False

        # 3. Check for matching ALLOW rules
        for rule in self.rules:
            if rule.effect == PolicyEffect.ALLOW and self._rule_matches(
                rule, subject, action, resource
            ):
                logger.debug(
                    "ABAC rule '{}' allowed access for '{}'",
                    rule.id,
                    subject.subject_id,
                )
                return True

        # Default Deny
        logger.info(
            "Default-deny: No rule matched for subject '{}' action '{}' on resource '{}:{}'",
            subject.subject_id,
            action,
            resource.resource_type,
            resource.resource_id,
        )
        return False

    def enforce(
        self,
        subject: SubjectAttributes,
        action: str,
        resource: ResourceBoundary,
    ) -> None:
        """Enforce policy and raise ABACAccessDeniedError on rejection."""
        allowed = self.evaluate(subject, action, resource)
        if not allowed:
            audit = SecurityAuditLogger.get_logger()
            audit.log_event(
                AuditEvent(
                    actor=subject.subject_id,
                    tenant=subject.organization_id,
                    action=f"abac.{action}",
                    resource_type=resource.resource_type,
                    resource_id=resource.resource_id,
                    outcome="denied",
                    metadata={
                        "project_id": resource.project_id,
                        "workspace_id": resource.workspace_id,
                    },
                )
            )
            raise ABACAccessDeniedError(
                f"ABAC Denied: Subject '{subject.subject_id}' unauthorized to '{action}' resource '{resource.resource_id}' ({resource.resource_type})"
            )

    def _rule_matches(
        self,
        rule: ABACPolicyRule,
        subject: SubjectAttributes,
        action: str,
        resource: ResourceBoundary,
    ) -> bool:
        # Match action
        if "*" not in rule.actions and action not in rule.actions:
            return False

        # Match resource type
        if (
            "*" not in rule.resource_types
            and resource.resource_type not in rule.resource_types
        ):
            return False

        # Match project containment if required
        if rule.require_same_project and subject.project_id != resource.project_id:
            return False

        # Match required roles
        if rule.required_roles and not any(
            r in subject.roles for r in rule.required_roles
        ):
            return False

        # Match clearance
        if rule.min_clearance:
            sub_val = CLEARANCE_HIERARCHY.get(subject.clearance, 0)
            req_val = CLEARANCE_HIERARCHY.get(rule.min_clearance, 0)
            if sub_val < req_val:
                return False

        return True


class JITElevationToken(BaseModel):
    """Temporary privilege elevation grant."""

    subject_id: str
    scope: str
    granted_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str
    approver_id: str
    reason: str


class JustInTimeElevationManager:
    """Manages short-lived Just-In-Time (JIT) privilege elevations for high-risk operations."""

    def __init__(self) -> None:
        # {(subject_id, scope): JITElevationToken}
        self._active_grants: dict[tuple[str, str], JITElevationToken] = {}

    def grant_elevation(
        self,
        subject_id: str,
        scope: str,
        duration_minutes: int = 15,
        reason: str = "Emergency maintenance",
        approver_id: str = "security_lead",
    ) -> JITElevationToken:
        """Grant temporary privilege elevation to a subject for a specific scope."""
        bounded_duration = min(60, max(1, duration_minutes))
        now = datetime.now(UTC)
        expiry = now + timedelta(minutes=bounded_duration)

        grant = JITElevationToken(
            subject_id=subject_id,
            scope=scope,
            granted_at=now.isoformat(),
            expires_at=expiry.isoformat(),
            approver_id=approver_id,
            reason=reason,
        )
        self._active_grants[(subject_id, scope)] = grant

        logger.warning(
            "JIT elevation granted for subject '{}' scope '{}' for {}m by '{}'",
            subject_id,
            scope,
            bounded_duration,
            approver_id,
        )

        audit = SecurityAuditLogger.get_logger()
        audit.log_event(
            AuditEvent(
                actor=approver_id,
                action="security.jit_elevation_granted",
                resource_type="elevation_token",
                resource_id=f"{subject_id}:{scope}",
                outcome="granted",
                metadata={
                    "subject_id": subject_id,
                    "scope": scope,
                    "duration_minutes": bounded_duration,
                    "reason": reason,
                    "expires_at": expiry.isoformat(),
                },
            )
        )
        return grant

    def is_elevated(self, subject_id: str, scope: str) -> bool:
        """Check if active unexpired elevation exists for the subject and scope."""
        key = (subject_id, scope)
        grant = self._active_grants.get(key)
        if not grant:
            return False

        try:
            expiry = datetime.fromisoformat(grant.expires_at.replace("Z", "+00:00"))
            if datetime.now(UTC) < expiry:
                return True
        except Exception:
            pass

        # Expired - clean up
        self._active_grants.pop(key, None)
        return False

    def revoke_elevation(
        self, subject_id: str, scope: str, actor: str = "admin"
    ) -> bool:
        """Revoke active JIT elevation early."""
        key = (subject_id, scope)
        if key in self._active_grants:
            self._active_grants.pop(key)
            logger.info("JIT elevation revoked for '{}:{}'", subject_id, scope)
            audit = SecurityAuditLogger.get_logger()
            audit.log_event(
                AuditEvent(
                    actor=actor,
                    action="security.jit_elevation_revoked",
                    resource_type="elevation_token",
                    resource_id=f"{subject_id}:{scope}",
                    outcome="revoked",
                )
            )
            return True
        return False
