# AmberClaw AI OS

[![Version](https://img.shields.io/badge/version-2026.0.1-blue.svg)](pyproject.toml)
[![Status](https://img.shields.io/badge/status-stabilization-green.svg)](AI_HANDOFF.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security](https://img.shields.io/badge/security-zero--trust-red.svg)](SECURITY.md)

AmberClaw is an open, self-hosted, zero-trust AI operating system and agent runtime designed for developers and teams needing private, auditable automation across language models, tools, sandboxes, and messaging channels.

Current test status: **1,602 passed** offline unit, integration, and security tests on 8 November 2026. Zero Ruff errors across 687 files and zero mypy errors across 489 source files under strict type checking. For dated verification evidence and release notes, see [AI_HANDOFF.md](AI_HANDOFF.md) and [docs/release-notes-stabilization.md](docs/release-notes-stabilization.md).

---

## Table of Contents

- [Core Principles](#core-principles)
- [System Architecture](#system-architecture)
- [Feature and Isolation Matrix](#feature-and-isolation-matrix)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Configuration Reference](#configuration-reference)
- [Command Line Interface (CLI)](#command-line-interface-cli)
- [API Gateway Reference](#api-gateway-reference)
- [Execution Sandboxes and Isolation](#execution-sandboxes-and-isolation)
- [Memory and Storage Architecture](#memory-and-storage-architecture)
- [Supported Messaging Channels](#supported-messaging-channels)
- [Testing and Quality Verification](#testing-and-quality-verification)
- [Security and Auditing](#security-and-auditing)
- [Documentation](#documentation)
- [License](#license)

---

## Core Principles

- **Security by Construction**: Agent tools and actions execute under Linux kernel Landlock LSM filesystem confinement or sandboxed microVMs, with seccomp syscall filters and strict outbound network policies.
- **Auditable State Transitions**: Privileged actions, tool invocations, and secret accesses write append-only JSONL audit events secured with SHA-256 cryptographic hash chaining.
- **Provider-Agnostic Execution**: Dynamic LLM routing via LiteLLM supports local models (Ollama, vLLM) and hosted APIs (OpenAI, Anthropic, Gemini, Groq, DeepSeek) with automated circuit breaking and failover.
- **Multi-Tier Persistent Memory**: Hybrid storage combining SQLite SessionDB with FTS5 full-text indexing, vector stores (Chroma, LanceDB), graph memory, and GDPR-compliant data deletion.
- **Decoupled Asynchronous Kernel**: Central event bus links transport channels, agent planning loops, background cron runners, and monitoring services without tight runtime coupling.

---

## System Architecture

AmberClaw separates messaging ingress, agent execution planning, tool isolation, and data persistence into modular subsystems.

```
+-------------------------------------------------------------------------+
|                  Inbound Transports & Gateway Subsystem                 |
|   FastAPI REST API  |  Web Dashboard SPA  |  CLI  |  Messaging Channels |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                    Asynchronous Message Bus & Kernel                    |
|       Topic Routing  |  Concurrency Supervisors  |  Event Dispatch      |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                         Agent Planning Engine                           |
|   ReAct / Plan-and-Execute  |  Graph Planner  |  Subagent Delegation    |
|   Context Budget Tracker    |  Reflection     |  Skill Registry         |
+------------------+----------------------------------+-------------------+
                   |                                  |
                   v                                  v
+----------------------------------+ +------------------------------------+
|     Memory & Context Store       | |     Zero-Trust Isolation Layer     |
| - SQLite SessionDB (FTS5 WAL)    | | - Landlock LSM Confinement         |
| - Vector RAG (Chroma / LanceDB)  | | - Seccomp Filters (execve/execveat)|
| - Knowledge Graph Store          | | - Dynamic Sandboxes (Docker/Modal) |
| - GDPR Erasure Handlers          | | - SHA-256 Hash-Chained Audit Log   |
+----------------------------------+ +------------------------------------+
```

### Subsystem Overview

1. **Kernel and Event Bus (`src/amberclaw/core/`)**:
   Coordinates service lifecycles, manages task supervision trees, and routes messages asynchronously between channels and agent loops.
2. **Agent Planning and Reasoning (`src/amberclaw/agent/`)**:
   Provides ReAct execution loops, subagent coordination, prompt caching, tool validation, and memory nudges.
3. **Security and Sandboxing (`src/amberclaw/security/`, `src/amberclaw/terminal/`)**:
   Enforces file path confinement, drops Linux capabilities, inspects network egress, redacts secrets, and runs untrusted code in isolated containers or WebAssembly.
4. **Memory Engine (`src/amberclaw/memory/`)**:
   Manages session history, conversation context windows, vector embedding retrieval, and entity relationship graphs.
5. **Channels (`src/amberclaw/channels/`)**:
   Provides bidirectional adapters for Slack, Discord, Telegram, Matrix, WhatsApp, Email, Feishu, DingTalk, and MoChat.
6. **API Gateway (`src/amberclaw/api/`)**:
   FastAPI web service exposing OpenAPI 3.1 endpoints, WebSocket streaming, JWT/API key authentication, rate limiting, and Prometheus metrics.

---

## Feature and Isolation Matrix

| Capability | Status | Implementation Details |
|---|:---:|---|
| **Landlock LSM Isolation** | `VERIFIED` | Linux kernel unprivileged filesystem containment ([`src/amberclaw/security/landlock.py`](src/amberclaw/security/landlock.py)) |
| **Seccomp Syscall Filtering** | `VERIFIED` | Blocks `execve`, `execveat`, and `ptrace` in sandboxed processes ([`src/amberclaw/security/sandbox.py`](src/amberclaw/security/sandbox.py)) |
| **Cryptographic Audit Log** | `VERIFIED` | Append-only SHA-256 hash-chained JSONL records ([`src/amberclaw/security/audit.py`](src/amberclaw/security/audit.py)) |
| **Secret and PII Redactor** | `VERIFIED` | Regex pattern matching and text sanitization ([`src/amberclaw/security/secret_scanner.py`](src/amberclaw/security/secret_scanner.py)) |
| **Encrypted Credential Vault** | `VERIFIED` | Fernet and KMS envelope encryption with versioned KEK/DEK keys ([`src/amberclaw/security/vault.py`](src/amberclaw/security/vault.py)) |
| **Execution Sandboxes** | `VERIFIED` | 9 backends: Local, Docker, SSH, Daytona, Singularity, Modal, Vercel, WASM, E2B |
| **SQLite SessionDB FTS5** | `VERIFIED` | Full-text indexed session storage with WAL journal mode ([`src/amberclaw/memory/session_db.py`](src/amberclaw/memory/session_db.py)) |
| **FastAPI Gateway & Auth** | `VERIFIED` | Bearer JWT, API keys, rate limiting, idempotency keys, OpenAPI 3.1 |
| **Multi-Channel Adapters** | `VERIFIED` | Slack, Telegram, Discord, Matrix, WhatsApp, Email (IMAP/SMTP), Feishu, DingTalk |
| **Observability** | `VERIFIED` | Prometheus metrics on `/metrics`, OpenTelemetry distributed tracing |
| **Web Dashboard** | `VERIFIED` | Browser UI served directly from the gateway at `/` |

For full specification details, see [FEATURE_MATRIX.md](FEATURE_MATRIX.md).

---

## Requirements

- **Operating System**: Linux (recommended for native Landlock LSM and seccomp features), macOS, or Windows.
- **Python**: Version 3.11 or newer.
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (recommended) or `pip`.
- **Optional Services**:
  - Docker daemon (for container sandbox execution)
  - Redis 5.0+ (for multi-worker message distribution)
  - Ollama or vLLM (for local model inference)

---

## Quickstart

### 1. Installation

Clone the repository and synchronize the Python environment using `uv`:

```bash
git clone https://github.com/krishujeniya/AmberClaw.git
cd AmberClaw

# Copy environment configuration template
cp .env.example .env

# Install dependencies and sync virtual environment
uv sync
```

### 2. Environment Configuration

Edit `.env` to configure your API keys or local model providers:

```bash
# Example minimal configuration for local Ollama usage
OLLAMA_BASE_URL=http://localhost:11434
ENVIRONMENT=development
LOG_LEVEL=INFO

# Or configure API keys for cloud providers:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run Diagnostic Check

Run the built-in diagnostic doctor to verify configuration, network access, and sandbox prerequisites:

```bash
uv run amberclaw doctor
```

### 4. Start the Gateway and Web Dashboard

Launch the FastAPI core engine and dashboard interface:

```bash
uv run amberclaw start --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in your web browser to access the Web Dashboard.

### 5. Interactive CLI Agent

Run an interactive conversational agent session in your terminal:

```bash
uv run amberclaw agent
```

---

## Configuration Reference

AmberClaw reads configuration settings from environment variables or a `.env` file via `pydantic-settings`.

### Core Settings

| Variable | Type | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | string | `development` | Environment mode (`development`, `staging`, `production`). |
| `LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `HEARTBEAT_INTERVAL_SEC` | integer | `5` | Background system heartbeat check frequency in seconds. |
| `MAX_AUTO_BUDGET_USD` | float | `5.0` | Maximum spend limit allowed per autonomous session. |

### Model Providers

| Variable | Type | Description |
|---|---|---|
| `OPENAI_API_KEY` | string | OpenAI API secret key. |
| `ANTHROPIC_API_KEY` | string | Anthropic API secret key. |
| `GEMINI_API_KEY` | string | Google Gemini API key. |
| `GROQ_API_KEY` | string | Groq cloud acceleration API key. |
| `DEEPSEEK_API_KEY` | string | DeepSeek API key. |
| `OLLAMA_BASE_URL` | string | Local Ollama endpoint URL (e.g. `http://localhost:11434`). |

### Security and Sandboxes

| Variable | Type | Default | Description |
|---|---|---|---|
| `ENABLE_CODE_EXECUTION` | boolean | `true` | Allows execution of sandboxed code tools. |
| `SANDBOX_RUNTIME` | string | `docker` | Sandbox backend (`docker`, `modal`, `gvisor`, `local`). |
| `EGRESS_BLOCKED` | boolean | `true` | Enforces network egress firewall for agent tools. |
| `JWT_SECRET_KEY` | string | None | Random 32+ byte key for API token signing. |
| `AUTH_CLIENT_ID` | string | None | OAuth2 / API client identifier. |
| `AUTH_CLIENT_SECRET` | string | None | OAuth2 / API client secret. |

---

## Command Line Interface (CLI)

The `amberclaw` CLI provides operations for managing agents, testing channels, querying memory, and running diagnostics.

### Core Commands

- `amberclaw start`: Start the API Gateway and Web Dashboard server.
  ```bash
  uv run amberclaw start --host 0.0.0.0 --port 8000
  ```
- `amberclaw doctor`: Run system checks for environment, sandboxes, and keys.
  ```bash
  uv run amberclaw doctor
  ```
- `amberclaw agent`: Start an interactive conversational agent in the terminal.
  ```bash
  uv run amberclaw agent
  ```
- `amberclaw status`: Display status of active background services, memory, and bus.
  ```bash
  uv run amberclaw status
  ```
- `amberclaw tui`: Launch the full-screen terminal user interface (Textual).
  ```bash
  uv run amberclaw tui
  ```
- `amberclaw scan-secrets`: Scan workspace files for accidentally committed credentials.
  ```bash
  uv run amberclaw scan-secrets
  ```

### Management Sub-Commands

- `amberclaw skill`: List, inspect, and test loaded agent skills.
- `amberclaw channels`: Test and inspect configured messaging channel adapters.
- `amberclaw provider`: Inspect LLM provider health metrics and circuit breaker status.
- `amberclaw budget`: View token spend and cost tracking summaries.
- `amberclaw db`: Run database schema migrations and integrity checks.
- `amberclaw backup`: Create snapshot backups of session databases and vector stores.
- `amberclaw restore`: Restore session data from an existing backup archive.
- `amberclaw cron`: Schedule, list, and trigger recurring background agent jobs.
- `amberclaw policy`: View and enforce organization role-based access control policies.

---

## API Gateway Reference

The AmberClaw Gateway runs on FastAPI and exposes REST and WebSocket endpoints. Interactive API documentation is accessible at `GET /docs` (Swagger UI) and `GET /redoc` (ReDoc).

### Key Endpoints

- `GET /health`: Basic health check returning status, uptime, and version.
- `GET /metrics`: Prometheus metrics exposition for system observability.
- `POST /api/v1/chat`: Send an inbound message and receive an agent response.
- `GET /api/v1/agents`: List configured agents, status, and assigned skills.
- `POST /api/v1/auth/token`: Issue Bearer JWT token using client credentials.
- `GET /api/v1/memory`: Query session history and long-term memory records.
- `DELETE /api/v1/memory`: Execute GDPR right-to-be-forgotten data deletion.
- `GET /api/v1/providers`: Retrieve provider latency, error rates, and health scores.
- `POST /api/v1/a2a`: Dispatch inter-agent communication messages.
- `GET /api/v1/sso/login`: Initiate SAML or OIDC enterprise Single Sign-On flow.

### Security Headers and Controls

All API requests enforce:
- Bearer JWT token or API Key authentication via `Authorization` header.
- 10MB maximum request payload enforcement.
- Rate limiting (default: 10 requests per minute on sensitive endpoints).
- Idempotency deduplication using `X-Idempotency-Key`.
- Explicit CORS origin validation (wildcard origins rejected in production).

---

## Execution Sandboxes and Isolation

AmberClaw provides isolation mechanisms to safely execute untrusted code:

1. **Linux Landlock LSM (`LocalTerminalBackend`)**:
   Uses the Linux kernel unprivileged Landlock LSM to restrict file access strictly to the active workspace directory. Symlinks pointing outside the workspace are blocked.
2. **Seccomp Filters**:
   Applies Berkeley Packet Filters (BPF) to block `execve`, `execveat`, and `ptrace` system calls in constrained Python worker processes.
3. **Container Sandboxing (`DockerTerminalBackend`)**:
   Spawns ephemeral Docker containers with read-only root filesystems, dropped capabilities, and memory/CPU limits.
4. **Cloud and WASM Backends**:
   Modular backends support running tasks in Modal, Daytona, Singularity, Vercel, or WebAssembly (via Wasmtime with fuel limits).

---

## Memory and Storage Architecture

AmberClaw uses a tiered memory model:

1. **SessionDB (`src/amberclaw/memory/session_db.py`)**:
   SQLite database operating in WAL (Write-Ahead Logging) journal mode with FTS5 full-text indexing for fast conversational recall.
2. **Vector RAG (`src/amberclaw/memory/rag_pipeline.py`)**:
   Semantic search pipeline integrating ChromaDB and LanceDB for document retrieval.
3. **Graph Memory (`src/amberclaw/memory/graph_memory.py`)**:
   Knowledge graph tracking entities, relationships, and temporal changes across sessions.
4. **GDPR Compliance**:
   Supports deterministic erasure of personal user data across relational tables, vector stores, and graph nodes upon request.

---

## Supported Messaging Channels

AmberClaw connects to third-party messaging platforms through bidirectional channel adapters:

- **Slack**: Events API and Web API integration via `slack-sdk`.
- **Telegram**: Long-polling and webhook updates via `python-telegram-bot`.
- **Discord**: Real-time websocket gateway bot integration.
- **Matrix**: End-to-end encrypted messaging via `matrix-nio`.
- **WhatsApp**: Webhook and bridge integration.
- **Email**: Inbound polling via IMAP4/SSL and outbound delivery via SMTP.
- **Enterprise Messengers**: Feishu, DingTalk, and MoChat adapters.

---

## Testing and Quality Verification

AmberClaw enforces strict quality gates on every change:

- **Test Suite**: **1,602 passed** offline unit, integration, and security tests.
- **Linter**: Zero Ruff errors across 687 files.
- **Formatter**: Code formatting enforced across all files.
- **Type Checker**: Strict mypy type checking with zero errors across 489 source files.
- **Test Ratchet**: Total assertions and passed test counts are monitored to prevent regressions.

### Running Verification Locally

Run the quality checks using `uv`:

```bash
# Linting check
uv run ruff check src/ tests/

# Formatting check
uv run ruff format --check src/ tests/

# Strict type checking (use repo lock on resource-constrained systems)
flock .planning/verification.lock uv run mypy src/

# Run complete test suite
flock .planning/verification.lock uv run pytest -q --tb=line
```

---

## Security and Auditing

- **Audit Trails**: Every sensitive action writes an immutable record to `.amberclaw/audit.jsonl` with previous-hash linkage to prevent modification.
- **Credential Protection**: Secrets stored in `.amberclaw/vault.enc` use AES-128 Fernet encryption or KMS envelope wrapping.
- **Secret Scanning**: Automated pre-commit scanning rejects accidental exposure of API keys, private keys, or passwords.
- **Security Policy**: For reporting vulnerabilities, consult [SECURITY.md](SECURITY.md).

---

## Documentation

Full documentation is built with MkDocs Material:

```bash
uv run mkdocs serve
```

Documentation topics include:
- [System Architecture](docs/architecture.md)
- [Enterprise SSO Setup](docs/sso.md)
- [Disaster Recovery Runbook](docs/runbooks/disaster_recovery_runbook.md)
- [Upgrade and Stabilization Guide](docs/upgrade-stabilization.md)
- [Local Verification Evidence](AI_HANDOFF.md)

---

## License

AmberClaw is open-source software licensed under the [MIT License](LICENSE).
