# ADR-0006: Security Audit Log Concurrency, Truncation Resistance, and External Anchoring

Date: 8 November 2026
Status: accepted for CL-007 audit integrity implementation

## Context and Problem Statement
Observation A07 and CL-007 identified operational risks in the security audit logging architecture:
1. `src/amberclaw/security/audit.py` previously read the last entry from `audit.jsonl` and appended a hash-chained record without concurrency control. Multiple background workers or CLI processes logging events concurrently risked reading the same tail hash, producing forked chains and broken verification.
2. The audit trail was advertised as immutable; in reality, hash-chaining alone provides *tamper-evidence*, not physical write-once immutability. An adversary with filesystem write access could truncate the tail of the log file without breaking the internal hash continuity of the remaining prefix.
3. Downstream governance and compliance workflows lacked a portable receipt format to verify that a specific sensitive action (e.g., destructive tool execution, key access) was recorded without exporting raw audit logs containing operational metadata.

## Decision
1. **Multi-Process Write Serialization via File Locking**:
   - `SecurityAuditLogger.log_event` acquires an exclusive cross-process advisory lock (`fcntl.flock(LOCK_EX)` on POSIX systems) on `.audit.lock` before reading the last entry.
   - The transaction calculates the monotonic index and SHA-256 hash, appends the serialized JSON record, flushes the user-space buffer, and executes `os.fsync` before releasing the lock.
   - This ensures linear serializability across concurrent worker processes without forks or dropped entries.

2. **Truncation Detection via Cryptographic Anchor Receipts**:
   - Implemented `create_anchor_receipt() -> AuditAnchorReceipt`, recording `anchor_index`, `anchor_hash`, `record_count`, and UTC timestamp.
   - `verify_integrity` accepts an optional `expected_anchor: AuditAnchorReceipt`. Verification verifies both internal hash continuity and exact correspondence with the anchor index and terminal hash. Tail truncation or prefix substitution immediately fails verification.

3. **Portable Event Receipts and Secret Scrubbing**:
   - Implemented `export_event_receipt(event) -> dict[str, Any]` and `verify_receipt(receipt) -> bool`.
   - Privileged operations emit portable receipts linking actor, tenant, action, outcome, and cryptographic proof.
   - Sensitive credentials and keys matching `SECRET_PATTERNS` are scrubbed before payload hashing and disk persistence.

## Consequences
- Concurrent workers can log events at high throughput without risk of chain forking or index collisions.
- Truncation attacks are deterministically detected when verified against external anchors or checkpoints.
- Public/governance proof receipts can be shared without exposing internal infrastructure paths or credentials.
