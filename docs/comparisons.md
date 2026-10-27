# Ecosystem Comparison & Differentiation

AmberClaw is purpose-built as a **Zero-Trust Autonomous Agent Runtime**, contrasting with general orchestration libraries or UI-only wrappers.

---

## 📊 Feature Comparison Matrix

| Architectural Capability | AmberClaw | LangChain / LangGraph | CrewAI | AutoGen | Open WebUI |
|---|:---:|:---:|:---:|:---:|:---:|
| **Zero-Trust Process Sandboxing** | ✅ 9 Sandboxes (Landlock, WASM, Docker, E2B, Modal) | ❌ Unsandboxed | ❌ Unsandboxed | ⚠️ Docker only | ❌ None |
| **Cryptographic Audit Trail** | ✅ SHA-256 Chained JSONL | ❌ Standard logging | ❌ None | ❌ None | ❌ None |
| **Tamper-Evident Memory** | ✅ SQLite FTS5 SessionDB | ⚠️ In-memory / Basic | ⚠️ Basic Vector | ⚠️ Basic Vector | ⚠️ SQLite Chat |
| **Multi-Channel Adapters** | ✅ Discord, Slack, Telegram, Matrix, Feishu, Email | ❌ Framework only | ❌ Framework only | ❌ Framework only | ❌ Web only |
| **Built-in Web Dashboard SPA** | ✅ Native Glassmorphism UI | ❌ Third-party (LangSmith) | ❌ Third-party | ❌ Third-party (Studio) | ✅ Built-in |
| **Built-in CLI Doctor** | ✅ `amberclaw doctor` | ❌ None | ❌ None | ❌ None | ❌ None |
| **Programmatic Client SDK** | ✅ Async Python & REST SSE | ⚠️ Library call | ⚠️ Library call | ⚠️ Library call | ⚠️ REST API |
| **GDPR Memory Deletion** | ✅ `DELETE /api/v1/memory` | ❌ Manual | ❌ Manual | ❌ Manual | ❌ Manual |

---

## 🎯 When to Use AmberClaw

- **Private & Air-Gapped Deployments**: When you cannot send raw execution data to closed third-party SaaS platforms.
- **High-Risk Autonomous Actions**: When agents need to execute shell commands, write code, and call external APIs with hard OS-level filesystem and network containment.
- **Enterprise Multi-Channel Operations**: When your organization interacts with AI agents across Discord, Telegram, Slack, Matrix, and internal Webhooks from a single unified runtime.
