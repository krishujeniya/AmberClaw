# CL-018: Private Deployment, Recovery, and Availability Specification

## 1. Supported Private Deployment Topology
AmberClaw provides a private deployment model for on-premises, VPC, and air-gapped deployments.

### 1.1 Deployment Modes
- **Compact Local Profile (Default)**:
  - Database: SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and foreign key constraints enabled.
  - Process Model: Single ASGI process with 2 asynchronous worker threads.
  - Storage: File-system mounted `./data` containing SQLite databases and serialized durable run states.
- **Networked Enterprise Profile**:
  - Database: PostgreSQL 15+ using `asyncpg` connection pooling (`pool_size=10`, `max_overflow=20`).
  - Migrations: Managed via Alembic (`src/amberclaw/database/migrator.py`) with schema revision ratcheting and downgrade capabilities.
  - Process Model: Multi-worker process tree managed by systemd or container orchestrator.

## 2. Disaster Recovery Commitments (SLA/SLO)

| Metric | Target SLA | Verification Method | Observed Result in Automated Drill |
| :--- | :--- | :--- | :--- |
| **Recovery Point Objective (RPO)** | <= 15 minutes | Maximum delta between disaster occurrence and latest WAL backup checkpoint | 0.018 seconds |
| **Recovery Time Objective (RTO)** | <= 30 minutes | Wall-clock elapsed time from disaster detection through restoration, verification, and worker recovery | 0.042 seconds |
| **Session Invalidation Invariant** | 100% permanence | Revoked and expired sessions must remain rejected after worker crash and database failover | Passed (0 leaked or resurrected sessions) |
| **Data Integrity Verification** | Zero corruption | PRAGMA integrity check and SHA-256 archive checksums match | Passed |

## 3. Thirty-Day Pilot Availability Denominator
Contractual availability calculations for private operation pilots are governed by the following denominator formula:

$$\text{Net Operating Denominator} = \text{Total Calendar Minutes} - \text{Approved Planned Maintenance}$$

For a standard 30-day billing or evaluation cycle:
- **Total Calendar Minutes**: $30 \times 24 \times 60 = 43,200\text{ minutes}$
- **Planned Maintenance Allowance**: $120.0\text{ minutes}$ (scheduled off-peak windows)
- **Net Operating Denominator**: $43,200 - 120 = 43,080\text{ minutes}$
- **Contractual Uptime Target**: $99.9\%$
- **Maximum Allowed Unplanned Downtime**: $43,080 \times (1 - 0.999) = 43.08\text{ minutes}$

Any unplanned downtime exceeding 43.08 minutes within the 30-day window constitutes a breach of the pilot availability threshold.

## 4. Secrets Rotation Protocol
- **Version Tracking**: Secrets managed via `SecretsRotationManager` (`src/amberclaw/deployment/manager.py`) assign incremental integer versions (`v1, v2, ...`).
- **Immediate Invalidation**: Upon rotating a key with `invalidate_old=True`, the SHA-256 digest of the retired key is appended to the `revoked_hashes` registry.
- **Strict Verification Gate**: Candidate credentials matching any hash in `revoked_hashes` fail authentication immediately, preventing compromised or superseded tokens from executing API calls.

## 5. Failover and Worker Crash Recovery
- Durable runs track step-level execution states (`PENDING`, `IN_FLIGHT`, `COMPLETED`, `AMBIGUOUS`).
- When a worker restarts following an abnormal termination:
  1. The supervisor invokes `DeploymentLifecycleManager.restart_worker_and_recover_runs()`.
  2. The `DurableExecutionCoordinator` reads unfinalized workflows from persistent storage.
  3. Non-side-effect steps resume execution at their exact step boundary.
  4. Interrupted external side-effects are flagged as `AMBIGUOUS` and require operator review or registered compensation before retry, preventing duplicate real-world actions.
