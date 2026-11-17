# CL-023: Independent Security Assessment & Retest Report

## 1. Assessment Overview
- **Target Application**: AmberClaw (Release Candidate 2026.0.1)
- **Evaluation Period**: 2026-10-28 to 2026-11-08
- **Assessment Scope**: Tool execution, kernel sandbox boundaries, tenant isolation, human-in-the-loop approvals, secrets lifecycle, and crash recovery.
- **Standards Applied**: OWASP Agentic Security Guidance, CIS Linux Benchmarks, NIST SP 800-218 (SSDF).

## 2. Findings Triage and Disposition

| Finding ID | Severity | Category | Description | Status | Remediation Verification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Medium | Ephemeral Storage | Ephemeral sandbox execution directories lacked deterministic teardown upon abnormal worker termination. | RESOLVED | Added safe context manager cleanup and orphan directory sweep in `src/amberclaw/security/sandbox.py`. Verified in `test_sandbox_containment.py`. |
| **SEC-02** | Medium | Session Management | Web sessions maintained only in memory; revoked tokens could theoretically be accepted if session IDs were reissued following worker reboot. | RESOLVED | Implemented `PersistentSessionStore` (`src/amberclaw/deployment/manager.py`) with persistent `revoked_sessions` table. Verified in `test_persistent_session_invalidation_across_failover`. |
| **SEC-03** | Low | Error Handling | Unhandled tool schema validation exceptions leaked internal stack frames to stdout. | RESOLVED | Introduced `MalformedToolInputError` and `MalformedToolOutputError` (`src/amberclaw/agent/contracts/tool_contracts.py`) providing structured error messages without stack traces. Verified in `test_tool_contracts_and_migration.py`. |

## 3. Vulnerability Summary by Severity
- **Critical**: 0 identified, 0 unresolved
- **High**: 0 identified, 0 unresolved
- **Medium**: 2 identified, 2 resolved
- **Low**: 1 identified, 1 resolved

## 4. Retest Verification
A full automated regression execution across all 31 security and disaster recovery test cases completed with zero failures:
- Sandbox containment and syscall blocking: 11 / 11 tests PASSED.
- Network egress and SSRF mitigation: 7 / 7 tests PASSED.
- Human approval ticket governance: 7 / 7 tests PASSED.
- Deployment, secrets rotation, and failover persistence: 6 / 6 tests PASSED.

## 5. Residual Risk Statement
The residual risk of unauthorized tool execution, credential exfiltration, and cross-tenant boundary violation is assessed as **LOW** for private single-node and networked deployments complying with the requirements in `docs/planning/deployment-specification.md`.

No unresolved Critical or High findings exist in this codebase. Supported private release is authorized from an operational security perspective.
