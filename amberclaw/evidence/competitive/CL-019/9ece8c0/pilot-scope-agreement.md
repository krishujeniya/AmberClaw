# CL-019: Enterprise Bounded Pilot Scope and Governance Agreement

## 1. Scope and Objective
This bounded pilot agreement defines the operating constraints, data boundaries, and verification criteria for 4 consenting enterprise pilot organizations (FinTech, HealthTech, SecOps, CloudInfra).

## 2. Invariant Operating Boundaries
1. **Zero External Data Exfiltration**:
   - AmberClaw runs on customer-provided infrastructure (isolated VM or on-premises Kubernetes cluster).
   - All network egress from the execution sandbox is blocked at the kernel level via Linux seccomp and Landlock filters.
2. **Deterministic Operator Approval Gate**:
   - Any external mutation or destructive side-effect requires approval via cryptographic HMAC ticket resolution.
   - Runaway loops are terminated automatically upon exceeding the pre-allocated step count ceiling.
3. **Hard Spend Ceiling**:
   - Workflows operate under strict budget limits; runs abort immediately if token or currency spend exceeds reservation.
4. **Data Isolation & Deletion**:
   - All ephemeral runs, memory embeddings, and temporary credentials can be expunged via single-tenant deletion commands.

## 3. Success Metrics for Pilot Conclusion
- Minimum 80% unaided workflow completion on target recipes.
- Zero unauthorized mutations or uncontained process escapes across all pilot runs.
- Measured cost-per-success tracked and reconciled within 5% of actual inference provider charges.
