# AmberClaw AI OS

[![Version](https://img.shields.io/badge/version-2026.0.1-blue.svg)](pyproject.toml)
[![Verification](https://img.shields.io/badge/current_worktree-unverified-yellow.svg)](AI_HANDOFF.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security](https://img.shields.io/badge/security-policy-red.svg)](SECURITY.md)

AmberClaw is an open-source, self-hosted agent runtime and operating system built for engineering and operations teams that require private execution, verifiable audit trails, hard spend boundaries, and human oversight.

The repository contains historical evidence records for the 28-item competitive leadership backlog, tied to the `9ece8c0` checkpoint. The current worktree has uncommitted changes, and no GitHub Actions run has verified this revision. Historical test and quality results are documented in [AI_HANDOFF.md](AI_HANDOFF.md); they do not establish current verification.

---

## Table of Contents

- [Core Architectural Invariants](#core-architectural-invariants)
- [System Architecture](#system-architecture)
- [Private-Operations Recipes](#private-operations-recipes)
- [Controlled Comparative Benchmarks](#controlled-comparative-benchmarks)
- [Requirements & Modular Packaging](#requirements--modular-packaging)
- [Quickstart](#quickstart)
- [Configuration Reference](#configuration-reference)
- [Command Line Interface (CLI)](#command-line-interface-cli)
- [API Gateway Reference](#api-gateway-reference)
- [Execution Sandboxes and Containment](#execution-sandboxes-and-containment)
- [Memory and Knowledge Architecture](#memory-and-knowledge-architecture)
- [Supported Messaging Channels](#supported-messaging-channels)
- [Third-Party Extension Ecosystem](#third-party-extension-ecosystem)
- [Disaster Recovery and Operational SLAs](#disaster-recovery-and-operational-slas)
- [Testing and Verification](#testing-and-verification)
- [Documentation Index](#documentation-index)
- [License](#license)

---

## Core Architectural Invariants

1. **Kernel-Level Confinement and Network Egress Firewall**:
   Agent tools execute within unprivileged Linux Landlock LSM sandboxes and seccomp filters. File system access is restricted to declared workspace paths, and arbitrary network sockets are blocked by default.
2. **Tamper-Evident SHA-256 Merkle Audit Trails**:
   Every privileged action, tool execution, credential access, and policy evaluation writes append-only JSONL audit events. File-lock (`flock`) synchronization prevents multi-worker concurrency corruption, and external anchor receipts detect truncation.
3. **Unified Execution Runtime (`ChatRuntime`)**:
   A canonical execution path routes requests from the CLI, REST API, Web UI, and messaging channels through identical policy checks, memory context, and audit recording (documented in [ADR-0005](docs/adr/0005-unified-canonical-agent-runtime-routing.md)).
4. **Durable Execution and Side-Effect Safety**:
   Step execution and tool invocations use deterministic state tracking. Crashed worker processes resume from checkpoints without duplicating external actions, and pending human approvals persist across restarts (documented in [ADR-0007](docs/adr/0007-durable-runs-and-side-effect-safety.md)).
5. **Reviewable Human Approvals**:
   High-risk actions (file modifications, outbound network traffic, shell commands) generate structured `ApprovalTicket` records requiring human operator review before dispatch. The review interface adheres to WCAG 2.2 AA accessibility standards.
6. **Trustworthy Knowledge Grounding**:
   Information retrieval returns exact line-level file citations. The engine abstains when source evidence is missing or contains unresolved temporal contradictions, preventing invented facts.
7. **Hard Token and Budget Accounting**:
   Pre-execution budget reservations enforce spend limits. A 5% in-flight settlement grace prevents sudden aborts, and all failed attempts or retries are recorded in realized costs.

---

## System Architecture

AmberClaw separates ingress transports, execution planning, tool isolation, and data storage into decoupled subsystems.

```
+-------------------------------------------------------------------------+
|                  Inbound Transports & Gateway Subsystem                 |
|   FastAPI REST API  |  Web Mission Control  |  CLI  |  Channel Adapters |
|      (OpenAPI 3.1)  |      (WCAG 2.2 AA)    |       | (Slack/TG/Ding)   |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                    Canonical Runtime Layer (ChatRuntime)                |
|       Unified Policy Check  |  Tenant Context  |  Trace Correlation     |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                         Agent Planning Engine                           |
|   ReAct / Plan-and-Execute  |  Durable Step Graph  |  Subagent Delegation|
|   Context Budget Tracker    |  Reflection Loops    |  Skill Registry    |
+------------------+----------------------------------+-------------------+
                   |                                  |
                   v                                  v
+----------------------------------+ +------------------------------------+
|     Memory & Context Store       | |     Zero-Trust Isolation Layer     |
| - SQLite SessionDB (FTS5 WAL)    | | - Landlock LSM File Confinement    |
| - Vector RAG (Chroma / LanceDB)  | | - Seccomp Filters (execve/ptrace)  |
| - Knowledge Graph Store          | | - Container Sandboxes (Docker/WASM)|
| - Cross-Store GDPR Erasure       | | - SHA-256 Hash-Chained Audit Trail |
+----------------------------------+ +------------------------------------+
```

### Subsystem Directory Mapping

- **Runtime & Orchestration (`src/amberclaw/runtime/`)**: Canonical `ChatRuntime` protocol, durable execution store, and atomic pricing ledger.
- **Agent Planning (`src/amberclaw/agent/`)**: ReAct loops, planning graph, tool contracts, and migration adapters.
- **Security & Confinement (`src/amberclaw/security/`)**: Landlock containment, seccomp filters, audit logging, and `ToolApprovalManager`.
- **Memory & Retrieval (`src/amberclaw/memory/`)**: Session database with FTS5 search, vector embeddings, graph memory, and citation verification.
- **Channel Adapters (`src/amberclaw/channels/`)**: Adapters for Slack, Telegram, Discord, Matrix, DingTalk, Feishu, and Email.
- **API Gateway & Web UI (`src/amberclaw/api/`, `src/amberclaw/web/`)**: FastAPI routing, JWT/API key authentication, rate limiting, and the Mission Control web dashboard.
- **Operational Recipes (`src/amberclaw/recipes/`)**: Pre-built workflows for cited retrieval, incident investigation, and scheduled audits.
- **Deployment & Recovery (`src/amberclaw/deployment/`)**: Lifecycle management, secrets rotation, session store, and disaster recovery automation.

---

## Private-Operations Recipes

AmberClaw includes three complete private-operations workflows designed for production use:

1. **Cited Knowledge Retrieval (`CitedKnowledgeRecipe`)**:
   Answers questions exclusively from authorized internal documents, returning line-level citations. Detects conflicting information and abstains if documents lack clear chronological precedence.
2. **Incident Investigation & Remediation (`IncidentInvestigationRecipe`)**:
   Correlates application and system logs across failure timestamps, identifies root causes, and formats targeted remediation commands. Execution of remediation scripts requires explicit human ticket authorization.
3. **Scheduled Compliance Reporting (`ScheduledReportRecipe`)**:
   Collects operational metrics, verifies audit trail cryptographic integrity, and generates structured Markdown digests with token and financial expenditure accounting.

---

## Controlled Comparative Benchmarks

Controlled evaluations were performed across 5 agent platforms using identical hardware (4 vCPU, 8 GB RAM, NVMe) and local model inference (Qwen 2.5 7B Instruct GGUF, temperature 0.0) across 5 standard tasks executed in triplicate (75 runs total).

| Platform | Evaluated Version | Success Rate | 95% Wilson Interval | P95 Latency | Cost per Success | Audit Trail Architecture |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **AmberClaw** | 2026.0.1 (`9ece8c0`) | **15/15 (100.0%)** | [0.796, 1.000] | **14.85 s** | **$0.0031** | SHA-256 Merkle chain, append-only |
| **Agent Zero** | v0.7.2 | 12/15 (80.0%) | [0.548, 0.930] | 19.65 s | $0.0042 | Flat local text logs |
| **OpenClaw** | v1.4.0 | 10/15 (66.7%) | [0.417, 0.848] | 21.80 s | $0.0049 | SQLite runtime records |
| **Dify** | v0.10.2 | 11/15 (73.3%) | [0.481, 0.891] | 24.30 s | $0.0055 | PostgreSQL audit events |
| **Langflow** | v1.0.18 | 8/15 (53.3%) | [0.301, 0.752] | 27.90 s | $0.0068 | Session/memory state |

Complete benchmark methodology, task fixtures, and raw output files are documented in [evidence/competitive/CL-022/9ece8c0/](evidence/competitive/CL-022/9ece8c0/).

---

## Requirements & Modular Packaging

- **Operating System**: Linux (recommended for native Landlock LSM and seccomp features), macOS, or Windows.
- **Python**: Version 3.11 or newer.
- **Tooling**: [uv](https://github.com/astral-sh/uv) (recommended) or `pip`.

### Dependency Extras

AmberClaw's core installation includes 33 base packages, reducing cold-start time by 86.4% and baseline resident set size (RSS) by 56.5% compared to monolithic setups. Optional packages are grouped into extras:

```bash
# Minimal core install
uv pip install amberclaw

# Optional feature extras
uv pip install "amberclaw[data]"       # ChromaDB, LanceDB, NetworkX, Matplotlib
uv pip install "amberclaw[channels]"   # Slack, Telegram, Matrix, Discord
uv pip install "amberclaw[storage]"    # PostgreSQL, Redis async connectors
uv pip install "amberclaw[sandboxes]"  # Modal, Daytona, E2B microVMs
uv pip install "amberclaw[all]"        # Full complete suite
```

---

## Quickstart

### 1. Installation

```bash
git clone https://github.com/krishujeniya/AmberClaw.git
cd AmberClaw

# Copy default environment configuration
cp .env.example .env

# Synchronize virtual environment with uv
uv sync
```

### 2. Environment Setup

Configure your target model endpoints in `.env`:

```bash
# Local inference via Ollama or vLLM (Zero data leaves host)
OLLAMA_BASE_URL=http://localhost:11434
ENVIRONMENT=development
LOG_LEVEL=INFO

# Or cloud provider credentials:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GEMINI_API_KEY=AIza...
```

### 3. Run Diagnostic Check

Verify operating system capabilities, Landlock availability, and model connectivity:

```bash
uv run amberclaw doctor
```

### 4. Start the Service and Mission Control

Launch the API Gateway and Web UI:

```bash
uv run amberclaw start --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` to access the Mission Control workspace. Note that internal dashboard routes enforce `noindex, nofollow` to prevent indexing of internal operational consoles.

### 5. Interactive Terminal Agent

Run an interactive agent loop directly in the terminal:

```bash
uv run amberclaw agent
```

---

## Configuration Reference

Configuration settings are loaded from environment variables or `.env` using `pydantic-settings`.

### Core Settings

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | string | `development` | Environment mode (`development`, `staging`, `production`). |
| `LOG_LEVEL` | string | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `HEARTBEAT_INTERVAL_SEC` | integer | `5` | Background supervision pulse interval in seconds. |
| `MAX_AUTO_BUDGET_USD` | float | `5.0` | Maximum spend cap permitted per autonomous session. |

### Model Providers

| Variable | Type | Description |
| :--- | :--- | :--- |
| `OLLAMA_BASE_URL` | string | Local Ollama endpoint URL (e.g., `http://localhost:11434`). |
| `OPENAI_API_KEY` | string | OpenAI API secret key. |
| `ANTHROPIC_API_KEY` | string | Anthropic API secret key. |
| `GEMINI_API_KEY` | string | Google Gemini API key. |
| `GROQ_API_KEY` | string | Groq hardware accelerator API key. |
| `DEEPSEEK_API_KEY` | string | DeepSeek API key. |

### Security and Sandboxes

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENABLE_CODE_EXECUTION` | boolean | `true` | Allows execution of sandboxed code tools. |
| `SANDBOX_RUNTIME` | string | `docker` | Isolation engine (`docker`, `local`, `modal`, `wasm`). |
| `EGRESS_BLOCKED` | boolean | `true` | Restricts outbound network connections from sandbox. |
| `JWT_SECRET_KEY` | string | None | Random 32+ byte string for API token signing. |
| `AUTH_CLIENT_ID` | string | None | OAuth2 / API client identifier. |
| `AUTH_CLIENT_SECRET` | string | None | OAuth2 / API client secret. |

---

## Command Line Interface (CLI)

The `amberclaw` CLI provides commands for operations, diagnostics, and data maintenance.

### Primary Commands

- `amberclaw start`: Launch API Gateway and Web UI (`--host`, `--port`, `--workers`).
- `amberclaw doctor`: Run diagnostic suite on environment, permissions, and models.
- `amberclaw agent`: Start interactive command-line session.
- `amberclaw status`: Inspect health of background tasks, memory stores, and event queues.
- `amberclaw tui`: Open terminal dashboard interface.
- `amberclaw scan-secrets`: Run static regex scanner across workspace for credentials.

### Operational Subcommands

- `amberclaw db`: Database migrations and integrity checks.
- `amberclaw backup`: Create snapshot archive of SQLite and vector databases.
- `amberclaw restore`: Restore system state from an existing snapshot archive.
- `amberclaw policy`: View and enforce role-based access control rules.
- `amberclaw budget`: Display historical token consumption and spend ledgers.
- `amberclaw cron`: Manage recurring scheduled agent workflows.

---

## API Gateway Reference

AmberClaw's API gateway runs on FastAPI, providing REST endpoints, Server-Sent Events (SSE), and WebSockets. Interactive API documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Endpoints

- `GET /health`: System status, uptime, and version.
- `GET /metrics`: Prometheus metrics exposition.
- `POST /api/v1/chat`: Dispatch message to canonical `ChatRuntime` and receive response.
- `GET /api/v1/agents`: List active agents, configurations, and skill assignments.
- `POST /api/v1/auth/token`: Authenticate client credentials and issue Bearer JWT.
- `GET /api/v1/tickets`: Query pending human approval tickets for high-risk actions.
- `POST /api/v1/tickets/{id}/resolve`: Approve or reject a pending action ticket.
- `GET /api/v1/memory`: Search session history and knowledge embeddings.
- `DELETE /api/v1/memory`: Execute right-to-be-forgotten data erasure across stores.

### Security Controls

- Enforces Bearer JWT or API key on protected routes.
- Request payload ceiling enforced at 10 MB.
- Sensitive endpoints rate-limited to 10 requests per minute by default.
- Idempotency keys supported via `X-Idempotency-Key` header.
- CORS wildcard origins rejected in production mode.

---

## Execution Sandboxes and Containment

1. **Linux Landlock LSM (`LocalTerminalBackend`)**:
   Restricts filesystem reads and writes strictly to the declared project directory using unprivileged kernel LSM rules. Access to host paths (`/etc`, `/root`, `/home`) and outside symlinks is blocked.
2. **Seccomp Syscall Filtering**:
   Applies BPF filters in worker sub-processes to deny `execve`, `execveat`, and `ptrace` system calls.
3. **Container Sandboxing (`DockerTerminalBackend`)**:
   Runs commands inside ephemeral Docker containers with dropped capabilities, read-only root filesystems, and strict memory/CPU limits.
4. **Cloud & WASM Backends**:
   Optional execution adapters for WebAssembly (via Wasmtime with instruction fuel caps), Modal, Daytona, and Singularity.

---

## Memory and Knowledge Architecture

- **SessionDB (`src/amberclaw/memory/session_db.py`)**: SQLite operational database running with Write-Ahead Logging (WAL) and FTS5 full-text indexing.
- **Vector RAG (`src/amberclaw/memory/rag_pipeline.py`)**: Semantic similarity search with ChromaDB and LanceDB.
- **Knowledge Graph (`src/amberclaw/memory/graph_memory.py`)**: Entity-relationship storage modeling connections and temporal updates.
- **Data Deletion Engine**: Propagates data deletion requests across relational, vector, and graph stores to satisfy regulatory requirements.

---

## Supported Messaging Channels

- **Slack**: Events API and Web API integration via `slack-sdk`.
- **Telegram**: Long-polling and webhook handling via `python-telegram-bot`.
- **Discord**: WebSocket gateway bot connection.
- **Matrix**: End-to-end encrypted messaging via `matrix-nio`.
- **DingTalk & Feishu**: Enterprise chat webhooks and signature verification.
- **Email**: Inbound polling via IMAP4/SSL and delivery via SMTP.

---

## Third-Party Extension Ecosystem

AmberClaw extensions are structured packages containing a `plugin.yaml` manifest and an entrypoint script.

```yaml
name: jira_incident_sync
version: 1.0.0
description: "Synchronizes security incidents with external tracker"
entrypoint: main.py
capabilities:
  - filesystem_read
  - network_access
min_amberclaw_version: "2026.0.1"
license: "Apache-2.0"
```

- **Capability Isolation**: Declared capabilities (`filesystem_read`, `filesystem_write`, `network_access`, `env_read`) are enforced by the sandbox supervisor.
- **Mandatory Approval Interception**: Tools registered by third-party extensions with elevated risk ratings require explicit operator approval through `ToolApprovalManager` before dispatch.
- **Lifecycle Management**: Extensions can be installed, updated, or revoked without restarting the host process. Revoking a plugin immediately removes all associated tools.

---

## Disaster Recovery and Operational SLAs

AmberClaw includes a dedicated `DeploymentLifecycleManager` tested against failover and disaster scenarios:

- **Recovery Point Objective (RPO)**: Target <= 15 minutes. Measured in drills: **2.5 minutes**.
- **Recovery Time Objective (RTO)**: Target <= 30 minutes. Measured in drills: **4.2 minutes**.
- **Availability Target**: 99.9% availability across 43,080 operating monthly minutes (maximum 43.08 minutes unplanned downtime).
- **Session Revocation Guarantee**: Expired sessions and revoked API tokens remain invalid after node failover.
- **Audit Chain Continuity**: SHA-256 Merkle chain integrity is verified before and after recovery procedures.

---

## Testing and Verification

Run tests, lint, type checks, documentation builds, package builds, and container builds in GitHub Actions. The `CI` workflow runs on pull requests and pushes to `main` or `master`; use its **Run workflow** control for a manual run. It checks Python 3.11–3.13, installation paths, and builds wheel/sdist and the Docker image without publishing them. Package distributions are retained as workflow artifacts for 14 days.

The `Security Scan & Supply Chain` workflow runs on schedule, relevant pushes, or manual dispatch. Its Bandit, Gitleaks, dependency audit, license, and SBOM steps report through the Actions run. `Build Documentation` validates documentation changes on pull requests and pushes. Dependabot dependency update pull requests are subject to the same CI checks.

Release publication remains a separate GitHub Actions path: PyPI publication requires a published GitHub release, and GHCR publication occurs on eligible main pushes or releases. Check the relevant Actions run and its commit SHA before treating a build, update, or release as verified. No local test or build result is a substitute for those checks.

---

## Documentation Index

- [Competitive Research & Leadership Tracker](docs/planning/competitive-leadership-tracker.md): Complete backlog, competitor profiles, and verification status for CL-001 through CL-028.
- [System Architecture](docs/architecture.md): Subsystems, communication flows, and data schemas.
- [ADR-0005: Canonical Runtime Routing](docs/adr/0005-unified-canonical-agent-runtime-routing.md): Routing entry points through `ChatRuntime`.
- [ADR-0006: Audit Concurrency & Integrity](docs/adr/0006-audit-integrity-concurrency-anchoring.md): File-locked audit chains and external receipts.
- [ADR-0007: Durable Execution & Safety](docs/adr/0007-durable-runs-and-side-effect-safety.md): Durable runs, crash recovery, and idempotent execution.
- [Disaster Recovery Runbook](docs/runbooks/disaster_recovery_runbook.md): Step-by-step failover and restore instructions.
- [Enterprise SSO Guide](docs/sso.md): SAML 2.0 and OIDC configuration.
- [Verification Evidence](evidence/competitive/): Per-milestone execution logs, test outputs, and SHA-256 manifests.

---

## License

AmberClaw is open-source software licensed under the [MIT License](LICENSE).
For reporting security issues, please refer to [SECURITY.md](SECURITY.md).
