# AmberClaw AI OS

[![Version](https://img.shields.io/badge/version-2026.0.1-blue.svg)]()
[![Status](https://img.shields.io/badge/status-production--stabilization-success.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security](https://img.shields.io/badge/security-zero--trust-red.svg)](SECURITY.md)
[![Tests](https://img.shields.io/badge/tests-568%20passing-brightgreen.svg)]()

> **The open, self-hosted, zero-trust agent runtime for teams and individuals who need private, auditable AI automation across models, tools, and communication channels.**

---

## 🏛️ Core Pillars

1. **Secure by Construction** — Every agent action is authenticated, authorized, isolated (Linux Landlock LSM or container sandboxes), budgeted, and audited with SHA-256 hash chains.
2. **Runs Anywhere** — Seamless execution across local machines, servers, cloud developer environments, edge devices, and serverless backends.
3. **Any Model, Consistent Behavior** — Capability-aware LLM routing via LiteLLM supporting OpenAI, Anthropic, Ollama, vLLM, and local models.
4. **Persistent and Useful Memory** — SQLite SessionDB FTS5 full-text indexing, multi-scope memory management, and verifiable GDPR right-to-be-forgotten deletion.
5. **Action Transparency** — Structured JSONL audit trails, approval boards for high-risk actions, and Prometheus metrics for full operational visibility.
6. **Instant Activation** — Quick onboarding wizard (`amberclaw onboard`), built-in diagnostic doctor (`amberclaw doctor`), and zero-setup web dashboard SPA.

---

## 🛡️ Feature & Isolation Matrix

| Capability | Status | Specification / Engine |
|---|:---:|---|
| **Zero-Trust Landlock Isolation** | `VERIFIED` | Linux kernel Landlock filesystem confinement (`src/amberclaw/security/landlock.py`) |
| **Cryptographic Audit Logger** | `VERIFIED` | Append-only SHA-256 hash-chained JSONL logger (`src/amberclaw/security/audit.py`) |
| **Secret & PII Redactor** | `VERIFIED` | Automated regex scanner & text redaction (`src/amberclaw/security/secret_scanner.py`) |
| **Execution Sandboxes (9 Backends)** | `VERIFIED` | Local, Docker, SSH, Daytona, Singularity, Modal, Vercel, WASM, E2B |
| **SQLite SessionDB FTS5** | `VERIFIED` | Full-text indexed session memory with WAL journal (`src/amberclaw/memory/session_db.py`) |
| **FastAPI Gateway & Auth** | `VERIFIED` | Bearer JWT & API Key authentication, rate limiting, request timeout, idempotency |
| **Messaging Channels** | `VERIFIED` | Telegram, Discord, Matrix, Email, Feishu, DingTalk, MoChat, WhatsApp, Slack |
| **Observability & Metrics** | `VERIFIED` | Prometheus metrics exposition at `GET /metrics` and OpenAPI 3.1 exporter |
| **Web Dashboard SPA** | `VERIFIED` | Native dark glassmorphism dashboard UI served at `GET /` |

For full specification details, see [FEATURE_MATRIX.md](FEATURE_MATRIX.md).

---

## 🚀 Quickstart

### 1. Installation
We use [uv](https://github.com/astral-sh/uv) for fast and deterministic dependency management.

```bash
# Clone the repository
git clone https://github.com/krishujeniya/AmberClaw.git
cd AmberClaw

# Copy example environment file
cp .env.example .env

# Sync virtual environment and install dependencies
uv sync
```

### 2. Run Diagnostics
Verify configuration, provider keys, and sandbox prerequisites:

```bash
uv run amberclaw doctor
```

### 3. Start the Gateway & Web Dashboard
```bash
uv run uvicorn amberclaw.api.main:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` in your browser to access the Web Dashboard.

### 4. Interactive CLI Mode
```bash
uv run amberclaw agent
```

---

## 📚 Documentation

Build and serve the documentation locally with MkDocs:

```bash
uv run mkdocs serve
```

Visit `http://127.0.0.1:8000` to view the comprehensive guides, architecture deep-dive, API reference, and skill creation tutorials.

---

## 🧪 Testing & Quality Gates

Run the complete test suite (100% pass rate enforced):

```bash
uv run pytest
```

---

## 📄 License

AmberClaw is licensed under the [MIT License](LICENSE).
