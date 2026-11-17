# CL-028: Leadership Evidence Maintenance Schedule and Operational Policy

## 1. Governance Objectives
This maintenance schedule establishes recurring operational routines to ensure that competitive claims, security advisories, benchmark figures, and disaster recovery commitments remain truthful, reproducible, and compliant with repository invariants.

---

## 2. Recurring Operational Calendars

### 2.1 Weekly Dependency and Vulnerability Audit
- **Cadence:** Every Monday at 02:00 UTC (automated pipeline) with human triage by 12:00 UTC.
- **Scope:**
  - Automated scanner execution: `pip-audit`, `safety`, and Gitleaks scan.
  - Verification of SBOM packages against the National Vulnerability Database (NVD) and GitHub Advisory Database.
- **Service Level Agreements (SLAs):**
  - **Critical / High CVEs:** Immediate assignment to Security On-Call. Patch or mitigation required within 24 hours. Release hotfix within 48 hours.
  - **Medium CVEs:** Assigned to Component Maintainer. Triaged and patched within 14 calendar days.
  - **Low CVEs:** Evaluated during regular sprint cycles (30 calendar days).

### 2.2 Monthly Competitor Source Registry Refresh
- **Cadence:** First business day of each calendar month.
- **Scope:**
  - Inspection of upstream releases, changelogs, and security bulletins across all 20 tracked platforms (C01–C20).
  - Updating `source-freshness-registry.json` with new pinned versions, commits, license modifications, or lifecycle state transitions (e.g., archival, deprecation).
  - Removal of outdated claims in documentation when competitor capabilities or architecture evolve.

### 2.3 Quarterly Controlled Benchmark Refresh
- **Cadence:** Quarterly (January, April, July, October).
- **Execution Protocol:**
  - Run the standardized 5-task comparative test suite in triplicate across the 5 direct comparators (AmberClaw, Agent Zero, OpenClaw, Dify, Langflow).
  - Pin the exact local inference weights (Qwen 2.5 7B Instruct GGUF) and compute environment (4 vCPU, 8 GB RAM).
  - Recompute 95% Wilson confidence intervals, p95 latencies, and token cost metrics.
  - If a competitor closes an operational gap or improves performance, adjust comparison matrices and documentation accordingly.

### 2.4 Semi-Annual Disaster Recovery & Incident Drills
- **Cadence:** Semi-annually (May and November).
- **Execution Scope:**
  - Full failover drill from primary node to secondary replica.
  - Automated measurement of Recovery Point Objective (RPO <= 15 minutes) and Recovery Time Objective (RTO <= 30 minutes).
  - Verification that revoked API tokens and expired user sessions remain rejected post-recovery.
  - Verification of Merkle audit trail continuity across backup restoration.

---

## 3. Deprecation and Version Support Policy

### 3.1 Supported Release Horizon
- AmberClaw maintains the current major release branch and the immediate preceding minor release for security patches.
- Patch releases are strictly backward-compatible.

### 3.2 Breaking Changes & Migration Notice
- Deprecations of APIs, configuration schemas, or plugin contracts require a minimum of six months advance notice.
- Deprecated interfaces must log actionable migration warnings specifying the replacement pattern and the target removal version.
- Migration adapters (such as `LangGraphMigrationAdapter`) must be provided for deprecated formats during the deprecation period.
