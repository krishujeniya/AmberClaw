"""Role-based authorization and permissions for the AmberClaw Org hierarchy."""

from enum import StrEnum

from pydantic import BaseModel, Field


class OrgRole(StrEnum):
    ADMIN = "admin"
    DEPARTMENT_LEAD = "department_lead"
    STAFF_AGENT = "staff_agent"
    SPECIALIST_AGENT = "specialist_agent"
    INTERN_AGENT = "intern_agent"


class OrgPermission(StrEnum):
    DELEGATE = "delegate"
    APPROVE_BUDGET = "approve_budget"
    CROSS_DEPT_CALL = "cross_dept_call"
    EXECUTE_SYSTEM = "execute_system"
    READ_SENSITIVE = "read_sensitive"
    MANAGE_ORG = "manage_org"


ROLE_HIERARCHY_LEVELS: dict[OrgRole, int] = {
    OrgRole.ADMIN: 100,
    OrgRole.DEPARTMENT_LEAD: 80,
    OrgRole.STAFF_AGENT: 60,
    OrgRole.SPECIALIST_AGENT: 40,
    OrgRole.INTERN_AGENT: 20,
}

DEFAULT_ROLE_PERMISSIONS: dict[OrgRole, set[OrgPermission]] = {
    OrgRole.ADMIN: {
        OrgPermission.DELEGATE,
        OrgPermission.APPROVE_BUDGET,
        OrgPermission.CROSS_DEPT_CALL,
        OrgPermission.EXECUTE_SYSTEM,
        OrgPermission.READ_SENSITIVE,
        OrgPermission.MANAGE_ORG,
    },
    OrgRole.DEPARTMENT_LEAD: {
        OrgPermission.DELEGATE,
        OrgPermission.APPROVE_BUDGET,
        OrgPermission.CROSS_DEPT_CALL,
        OrgPermission.READ_SENSITIVE,
    },
    OrgRole.STAFF_AGENT: {
        OrgPermission.DELEGATE,
        OrgPermission.READ_SENSITIVE,
    },
    OrgRole.SPECIALIST_AGENT: {
        OrgPermission.DELEGATE,
    },
    OrgRole.INTERN_AGENT: set(),
}


class OrgPolicy(BaseModel):
    """Evaluates organizational access control and delegation policies."""

    allow_cross_dept_delegation: bool = Field(default=False)
    strict_hierarchy_enforcement: bool = Field(default=True)

    def has_permission(self, role: OrgRole, permission: OrgPermission) -> bool:
        """Check if role possesses a specific permission."""
        perms = DEFAULT_ROLE_PERMISSIONS.get(role, set())
        return permission in perms

    def can_delegate(
        self,
        from_role: OrgRole,
        to_role: OrgRole,
        same_department: bool,
        from_custom_perms: set[OrgPermission] | None = None,
    ) -> bool:
        """Evaluate if an agent with from_role can delegate to an agent with to_role."""
        all_perms = DEFAULT_ROLE_PERMISSIONS.get(from_role, set())
        if from_custom_perms:
            all_perms = all_perms | from_custom_perms

        # Base delegation permission check
        if OrgPermission.DELEGATE not in all_perms:
            return False

        # Department boundary check
        if not same_department and not (self.allow_cross_dept_delegation or OrgPermission.CROSS_DEPT_CALL in all_perms):
            return False

        # Hierarchy level check
        if self.strict_hierarchy_enforcement:
            from_lvl = ROLE_HIERARCHY_LEVELS.get(from_role, 0)
            to_lvl = ROLE_HIERARCHY_LEVELS.get(to_role, 0)
            # Cannot delegate down if from_lvl < to_lvl
            if from_lvl < to_lvl:
                return False

        return True
