# AmberClaw AI OS — Feature Capability Matrix

This document defines the verified capabilities, security boundaries, backend execution engines, messaging channels, and telemetry endpoints of the AmberClaw Autonomous Agent AI OS framework.

---

## 🛡️ Security & Isolation Controls

| Feature | Status | Specification / File Reference |
|---|---|---|
| Zero-Trust Landlock Sandboxing | VERIFIED | Unprivileged Linux filesystem sandbox in `src/amberclaw/security/landlock.py` |
| Symlink Escape Protection | VERIFIED | Canonical path resolution & containment in `src/amberclaw/agent/tools/filesystem.py` |
| Command Injection Prevention | VERIFIED | Destructive pattern blocking & argument safety in `src/amberclaw/agent/tools/shell.py` |
| Secret & PII Redactor | VERIFIED | Regex secret scanner & automatic text redactor in `src/amberclaw/security/secret_scanner.py` |
| Cryptographic Audit Logger | VERIFIED | Append-only SHA-256 hash-chained JSONL logger in `src/amberclaw/security/audit.py` |
| Mandatory API Authentication | VERIFIED | Bearer JWT & API Key dependency injection in `src/amberclaw/security/auth.py` |
| Production CORS Hardening | VERIFIED | Wildcard origin `*` rejection in production mode in `src/amberclaw/api/main.py` |
| Browser Security Headers | VERIFIED | HSTS, CSP, Referrer-Policy, Permissions-Policy, X-Frame-Options, XSS headers |
| Input & Rate Limit Controls | VERIFIED | 10 MB payload cap & 10 req/min rate limiter in `src/amberclaw/api/middleware.py` |

---

## ⚡ Execution Sandboxes & Backends

| Backend | Status | Specification / File Reference |
|---|---|---|
| Local Execution | VERIFIED | Subprocess workspace isolation in `src/amberclaw/terminal/local.py` |
| Docker Container | VERIFIED | Isolated Docker container runtime in `src/amberclaw/terminal/docker.py` |
| SSH Remote Shell | VERIFIED | Secure Paramiko SSH execution in `src/amberclaw/terminal/ssh.py` |
| Daytona Cloud Sandbox | VERIFIED | Cloud developer workspace environment in `src/amberclaw/terminal/daytona.py` |
| Singularity Container | VERIFIED | HPC Singularity/Apptainer container engine in `src/amberclaw/terminal/singularity.py` |
| Modal Cloud Sandbox | VERIFIED | Ephemeral serverless container runtime in `src/amberclaw/terminal/modal.py` |
| Vercel Code Sandbox | VERIFIED | Serverless micro-VM sandbox in `src/amberclaw/terminal/vercel.py` |
| WASM Wasmtime Sandbox | VERIFIED | Fuel-bounded WebAssembly micro-runtime in `src/amberclaw/terminal/wasm.py` |
| E2B Firecracker Sandbox | VERIFIED | Ephemeral microVM sandbox in `src/amberclaw/terminal/e2b.py` |
| Dynamic Backend Factory | VERIFIED | Single-entry backend selection in `src/amberclaw/terminal/factory.py` |

---

## 🧠 Memory, State & Governance

| Feature | Status | Specification / File Reference |
|---|---|---|
| SQLite SessionDB Engine | VERIFIED | WAL journal mode, FTS5 full-text search in `src/amberclaw/memory/session_db.py` |
| Session Memory Manager | VERIFIED | Thread-safe turn retrieval & persistence in `src/amberclaw/memory/sqlite_memory.py` |
| JSON State Store | VERIFIED | Thread-safe atomic JSON persistence helper in `src/amberclaw/storage/persistence.py` |
| Governance Approval Queue | VERIFIED | Human-in-the-loop approval ticket store in `src/amberclaw/governance/tickets.py` |
| Persistent Agent Store | VERIFIED | Agent profile persistence & retrieval in `src/amberclaw/api/v1/agents.py` |

---

## 🌐 Telemetry, Observability & Web Dashboard

| Feature | Status | Specification / File Reference |
|---|---|---|
| Prometheus Telemetry | VERIFIED | HTTP throughput, latency histograms, LLM token usage at `GET /metrics` |
| OpenAPI Specification | VERIFIED | OpenAPI 3.1.0 contract exporter with security schemes (`docs/openapi.json`) |
| Standardized Error Envelopes | VERIFIED | Uniform `{ "error": { "code", "message", "request_id" } }` payload responses |
| FastAPI Web Dashboard | VERIFIED | Dark glassmorphism SPA dashboard UI serving at `GET /` |
| Web Session Authentication | VERIFIED | Cookie-based session manager (`wses_...`) in `src/amberclaw/web/auth.py` |
| Provider Health Check | VERIFIED | Real-time LLM status endpoint at `GET /api/v1/providers/health` |
| LLM Cost Tracking | VERIFIED | Prompt/completion token usage logging in `src/amberclaw/providers/litellm_client.py` |

---

## 💬 Messaging Platform Channels

| Channel | Status | Reference |
|---|---|---|
| Telegram | VERIFIED | Async polling & webhook handler in `src/amberclaw/channels/telegram.py` |
| Discord | VERIFIED | Gateway websocket integration in `src/amberclaw/channels/discord.py` |
| Matrix | VERIFIED | Matrix-nio matrix protocol client in `src/amberclaw/channels/matrix.py` |
| Email | VERIFIED | SMTP / IMAP email channel in `src/amberclaw/channels/email.py` |
| Feishu / Lark | VERIFIED | Enterprise Feishu post & table adapter in `src/amberclaw/channels/feishu.py` |
| DingTalk | VERIFIED | DingTalk webhook listener in `src/amberclaw/channels/dingtalk.py` |
| MoChat | VERIFIED | Enterprise MoChat channel in `src/amberclaw/channels/mochat.py` |
| WhatsApp | VERIFIED | WhatsApp bridge client |
| Slack | VERIFIED | Slack SDK event listener |

---

## 🛠️ CLI Diagnostics & First-Run Setup

| Command | Description | Status |
|---|---|---|
| `amberclaw doctor` | System health check for config paths, workspace, provider API keys, and dependencies | VERIFIED |
| `amberclaw init` / `amberclaw onboard` | Non-destructive guided workspace initialization wizard | VERIFIED |
| `amberclaw scan-secrets` | Secret scanning CLI for workspace files | VERIFIED |
| `amberclaw agent` | Interactive CLI chat agent runner | VERIFIED |
