# Zero-Trust Architecture & System Design

AmberClaw is built on a **Decoupled Asynchronous Kernel** designed for security, isolation, and auditable agent execution.

---

## 🏛️ System Topology

```
┌─────────────────────────────────────────────────────────────┐
│                 Messaging Channels & API Gateway            │
│       (FastAPI, Slack, Discord, Telegram, Matrix, CLI)      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Inbound Messages
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Asynchronous Message Bus                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Agent Planning & Loop                       │
│    - ReAct / Plan-and-Execute Loop                          │
│    - Capability Routing via LiteLLM                         │
│    - 3-Layer SQLite SessionDB (FTS5 Indexing)               │
└──────────────────────────────┬──────────────────────────────┘
                               │ Tool Invocations
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Zero-Trust Isolation Layer                    │
│    - Landlock LSM Filesystem Containment                    │
│    - Egress Network Firewall & Socket Proxy                 │
│    - Regex PII & Secret Redactor                            │
│    - SHA-256 Hash-Chained JSONL Audit Log                   │
│    - Execution Sandboxes (Docker, WASM, Modal, E2B, etc.)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Security Boundaries & Controls

### 1. Landlock LSM & Path Containment
- Unprivileged Linux kernel Landlock LSM restricts agent file system access exclusively to the designated workspace.
- Symlinks pointing outside the workspace boundary are rejected automatically.

### 2. Append-Only Audit Logging
- Every privileged action, tool execution, and state change produces an immutable structured JSONL audit record.
- Records are secured with SHA-256 cryptographic hash-chaining to ensure tamper detection.

### 3. API Authentication & Defense-in-Depth
- All protected API routes enforce Bearer JWT or API Key authentication via `Depends(get_current_user)`.
- Middleware enforces a 10MB payload size limit, 10 req/min rate limiter, request timeouts (504 Gateway Timeout), and idempotency keys (`X-Idempotency-Key`).
- Production mode strictly rejects wildcard CORS origins (`*`).

### 4. Dynamic Sandbox Factory
Execution backends are dynamically selectable through `amberclaw.terminal.factory.get_terminal_backend(...)`:
- `LocalTerminalBackend` (Landlock isolated)
- `DockerTerminalBackend`
- `WasmTerminalBackend` (Fuel & epoch bounded via Wasmtime)
- `E2BTerminalBackend` (Firecracker microVMs)
- `ModalTerminalBackend`
- `VercelTerminalBackend`
- `DaytonaTerminalBackend`
- `SingularityTerminalBackend`
- `SshTerminalBackend`
