# Zero-Trust Architecture & System Design

AmberClaw is built on a **Decoupled Asynchronous Kernel** designed for security, isolation, and auditable agent execution.

The base-agent callback in `amberclaw.agent.core` receives `AgentMessage`
instances through `AgentNetworking`. Direct and topic-based delivery invoke
the same callback. The default handler logs receipt; it does not call an LLM.
If a callback raises, networking logs a delivery failure. Regression checks
for callback, direct, and broadcast delivery live in
`tests/unit/agent/test_core_networking.py`.

The legacy `core.orchestrator.Orchestrator` now adapts already constructed
`AgentLoop` and `ChannelManager` instances. Pass both as `agent=` and `channels=`
or call `configure(agent, channels)` before `start()`. They must share one
`MessageBus`. `stop()` cancels and awaits the adapter's tasks and closes agent
connections. Legacy `Message` input requires explicit channel, sender, and
recipient metadata; native `InboundMessage` also uses the shared bus.
The adapter is for trusted application code; transport ingress continues to
enforce channel sender allowlists. See [ADR-0001](adr/0001-reuse-bus-runtime-for-orchestrator.md).

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
