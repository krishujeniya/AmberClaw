"""Unit tests for Enterprise Compliance Policy Packs."""

from amberclaw.governance.policies import EnforcementAction, PolicyEngine
from amberclaw.governance.policy_packs import (
    ComplianceStandard,
    PolicyPackRegistry,
)


def test_hipaa_compliance_policy_pack() -> None:
    """Test HIPAA policy pack blocks PHI transmission."""
    engine = PolicyEngine()
    applied_count = PolicyPackRegistry.apply_pack(ComplianceStandard.HIPAA, engine)
    assert applied_count >= 2  # noqa: PLR2004

    # 1. Prohibited PHI transmission should be denied
    eval_result = engine.evaluate(
        action_name="message",
        content="Patient diagnosis: hypertension and ssn: 000-12-3456",
    )
    assert eval_result.is_allowed is False
    assert eval_result.enforcement == EnforcementAction.DENY
    assert "HIPAA-001-PHI-BLOCK" in eval_result.triggered_policies


def test_soc2_compliance_policy_pack() -> None:
    """Test SOC2 Type 2 policy pack enforces change management approval and privilege bounds."""
    engine = PolicyEngine()
    PolicyPackRegistry.apply_pack(ComplianceStandard.SOC2_TYPE2, engine)

    # 1. Production DB drop should require human approval
    eval_db = engine.evaluate(
        action_name="db_migrate",
        content="DROP TABLE user_sessions CASCADE;",
    )
    assert eval_db.requires_approval is True
    assert eval_db.enforcement == EnforcementAction.REQUIRE_APPROVAL
    assert "SOC2-001-PROD-MUTATION" in eval_db.triggered_policies

    # 2. Privilege escalation attempt should be denied
    eval_iam = engine.evaluate(
        action_name="grant_role",
        content="assign role:admin to subagent_worker",
    )
    assert eval_iam.is_allowed is False
    assert eval_iam.enforcement == EnforcementAction.DENY
    assert "SOC2-002-IAM-ESCALATION" in eval_iam.triggered_policies


def test_gdpr_compliance_policy_pack() -> None:
    """Test GDPR policy pack enforces cross-border transfer approvals and PII minimization."""
    engine = PolicyEngine()
    PolicyPackRegistry.apply_pack(ComplianceStandard.GDPR, engine)

    # Cross-border data sync
    eval_transfer = engine.evaluate(
        action_name="cloud_sync",
        content="s3 sync bucket to region:us-east-1",
    )
    assert eval_transfer.requires_approval is True
    assert "GDPR-001-CROSS-BORDER-TRANSFER" in eval_transfer.triggered_policies

    # High-risk ID minimization
    eval_id = engine.evaluate(
        action_name="store_memory",
        content="Extracted passport_num: K12345678",
    )
    assert eval_id.is_allowed is False
    assert eval_id.enforcement == EnforcementAction.DENY


def test_airgapped_compliance_policy_pack() -> None:
    """Test Air-Gapped policy pack blocks external socket and curl requests."""
    engine = PolicyEngine()
    PolicyPackRegistry.apply_pack(ComplianceStandard.AIR_GAPPED, engine)

    eval_curl = engine.evaluate(
        action_name="bash",
        content="curl https://api.openai.com/v1/chat/completions",
    )
    assert eval_curl.is_allowed is False
    assert eval_curl.enforcement == EnforcementAction.DENY
    assert "AIRGAP-001-ZERO-EGRESS" in eval_curl.triggered_policies
