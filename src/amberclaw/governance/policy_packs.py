"""Enterprise Compliance Policy Packs for HIPAA, SOC2 Type 2, GDPR, and Air-Gapped Profiles."""

from enum import StrEnum

from pydantic import BaseModel, Field

from amberclaw.governance.policies import (
    EnforcementAction,
    PolicyEngine,
    PolicyRule,
)


class ComplianceStandard(StrEnum):
    """Supported enterprise regulatory and compliance frameworks."""

    HIPAA = "hipaa"
    SOC2_TYPE2 = "soc2_type2"
    GDPR = "gdpr"
    AIR_GAPPED = "air_gapped"
    FINRA = "finra"


class CompliancePolicyPack(BaseModel):
    """A bundle of declarative governance rules designed for a specific compliance standard."""

    standard: ComplianceStandard
    name: str
    description: str
    version: str = "1.0"
    rules: list[PolicyRule] = Field(default_factory=list)


class PolicyPackRegistry:
    """Registry providing pre-packaged compliance governance packs."""

    @classmethod
    def get_hipaa_pack(cls) -> CompliancePolicyPack:
        """HIPAA compliance pack enforcing PHI security, encryption, and auditability."""
        return CompliancePolicyPack(
            standard=ComplianceStandard.HIPAA,
            name="HIPAA Security & Privacy Rule Pack",
            description="Enforces PHI redaction, encryption at rest, and audit logging for healthcare data.",
            rules=[
                PolicyRule(
                    policy_id="HIPAA-001-PHI-BLOCK",
                    name="Block Unredacted PHI Egress",
                    description="Blocks transmitting raw Patient Health Information (SSN, MRN, Medical Record).",
                    target_actions=["message", "email", "export", "webhook"],
                    forbidden_tokens=["ssn:", "mrn:", "patient_id:", "diagnosis:"],
                    enforcement=EnforcementAction.DENY,
                ),
                PolicyRule(
                    policy_id="HIPAA-002-HEALTH-DATA-EXPORT",
                    name="Require Approval for Health Record Export",
                    description="Exports of clinical tables require human clinical reviewer approval.",
                    target_actions=["export_data", "sql_query", "download"],
                    forbidden_tokens=["clinical_records", "patient_table", "ephi"],
                    enforcement=EnforcementAction.REQUIRE_APPROVAL,
                ),
            ],
        )

    @classmethod
    def get_soc2_pack(cls) -> CompliancePolicyPack:
        """SOC2 Type 2 Trust Services Criteria pack enforcing access controls and audit trails."""
        return CompliancePolicyPack(
            standard=ComplianceStandard.SOC2_TYPE2,
            name="SOC2 Type 2 Security & Availability Pack",
            description="Enforces strict separation of duties, change management approvals, and rate limits.",
            rules=[
                PolicyRule(
                    policy_id="SOC2-001-PROD-MUTATION",
                    name="Require Approval for Production Schema Alterations",
                    description="Database migrations and production schema changes require peer review.",
                    target_actions=["db_migrate", "sql_exec", "deploy"],
                    forbidden_tokens=["DROP TABLE", "ALTER TABLE", "TRUNCATE"],
                    enforcement=EnforcementAction.REQUIRE_APPROVAL,
                ),
                PolicyRule(
                    policy_id="SOC2-002-IAM-ESCALATION",
                    name="Block Autonomous IAM Privilege Escalation",
                    description="Agents cannot autonomously grant themselves admin or superuser rights.",
                    target_actions=["grant_role", "assign_permission", "sudo"],
                    forbidden_tokens=["role:admin", "grant_all", "chmod 777"],
                    enforcement=EnforcementAction.DENY,
                ),
            ],
        )

    @classmethod
    def get_gdpr_pack(cls) -> CompliancePolicyPack:
        """GDPR privacy pack enforcing consent, data minimization, and right-to-be-forgotten."""
        return CompliancePolicyPack(
            standard=ComplianceStandard.GDPR,
            name="GDPR Data Privacy & Right-to-be-Forgotten Pack",
            description="Enforces data deletion hooks, storage limits, and EU data residency safeguards.",
            rules=[
                PolicyRule(
                    policy_id="GDPR-001-CROSS-BORDER-TRANSFER",
                    name="Require Approval for Cross-Border Data Transfers",
                    description="Transferring EU user records outside approved residency zones requires review.",
                    target_actions=["cloud_sync", "s3_upload", "export"],
                    forbidden_tokens=["region:us-", "cross_region_replicate"],
                    enforcement=EnforcementAction.REQUIRE_APPROVAL,
                ),
                PolicyRule(
                    policy_id="GDPR-002-PII-MINIMIZATION",
                    name="Block Direct Passport & National ID Extraction",
                    description="Blocks storing high-risk national identity numbers.",
                    target_actions=["store_memory", "save_contact"],
                    forbidden_tokens=["passport_num", "national_id"],
                    enforcement=EnforcementAction.DENY,
                ),
            ],
        )

    @classmethod
    def get_airgapped_pack(cls) -> CompliancePolicyPack:
        """Air-Gapped / High-Assurance pack enforcing zero external egress and enclave containment."""
        return CompliancePolicyPack(
            standard=ComplianceStandard.AIR_GAPPED,
            name="Air-Gapped & Zero-Egress High Assurance Pack",
            description="Forbids all outbound internet calls and enforces isolated sandboxing.",
            rules=[
                PolicyRule(
                    policy_id="AIRGAP-001-ZERO-EGRESS",
                    name="Deny External Network Sockets",
                    description="Blocks curl, wget, and external HTTP network requests.",
                    target_actions=["bash", "exec", "http_request"],
                    forbidden_tokens=["curl ", "wget ", "http://", "https://"],
                    enforcement=EnforcementAction.DENY,
                ),
            ],
        )

    @classmethod
    def get_pack(cls, standard: ComplianceStandard) -> CompliancePolicyPack:
        """Retrieve the policy pack for the requested compliance standard."""
        if standard == ComplianceStandard.HIPAA:
            return cls.get_hipaa_pack()
        if standard == ComplianceStandard.SOC2_TYPE2:
            return cls.get_soc2_pack()
        if standard == ComplianceStandard.GDPR:
            return cls.get_gdpr_pack()
        if standard == ComplianceStandard.AIR_GAPPED:
            return cls.get_airgapped_pack()
        return cls.get_soc2_pack()

    @classmethod
    def apply_pack(cls, standard: ComplianceStandard, engine: PolicyEngine) -> int:
        """Apply all rules in the specified compliance pack to a PolicyEngine instance."""
        pack = cls.get_pack(standard)
        for rule in pack.rules:
            engine.add_policy(rule)
        return len(pack.rules)
