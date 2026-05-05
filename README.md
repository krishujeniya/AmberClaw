# AmberClaw AI OS

[![Version](https://img.shields.io/badge/version-2026.0.1-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security](https://img.shields.io/badge/security-zero--trust-red.svg)](SECURITY.md)

**AmberClaw AI OS** is a fully modernized, enterprise-grade personal AI assistant framework designed for 2026 standards. It acts as an operating system that runs continuous background AI processes, tracks long-term context using a 3-layer memory architecture, and ensures absolute safety with zero-trust execution environments.

## Features
- **Kernel-Level Orchestration**: Fast asynchronous `HeartbeatEngine` schedules and tracks subagent lifecycles natively via Python `asyncio`.
- **Zero-Trust Governance**: The `GovernanceBoard` halts risky or expensive operations for human-in-the-loop approval.
- **Sandboxed Execution**: Subagents write and execute code in isolated containers via `CodeSandbox`.
- **Ubiquitous Memory**: 3-layer semantic persistence powered by `mem0ai` and `ChromaDB`.
- **Model Agnostic Routing**: Utilize OpenAI, Anthropic, Gemini, or Local Ollama models interchangeably via `LiteLLM`.

## Quickstart

### 1. Installation
We use [uv](https://github.com/astral-sh/uv) for lightning-fast dependency management.

```bash
# Clone the repository
git clone https://github.com/krishujeniya/AmberClaw.git
cd AmberClaw

# Copy env template
cp .env.example .env

# Install dependencies and sync virtual environment
make install
```

### 2. Booting the OS
Start the AmberClaw Gateway and core OS engines:

```bash
make dev
```

Alternatively, check the system status via the Typer CLI:

```bash
make cli
```

## Production Deployment

We ship production-ready configurations out of the box.

### Docker
```bash
# Spin up the OS Gateway and Vector Memory DB
make docker-up
```

### Kubernetes
We provide official Helm charts in `deploy/k8s/helm`.
```bash
helm install amberclaw ./deploy/k8s/helm -f deploy/k8s/helm/values.yaml
```

## Project Structure
AmberClaw adheres to strict domain-driven design:
- `src/amberclaw/agent/`: ReAct planning, delegation, and learning logic.
- `src/amberclaw/api/`: FastAPI Gateway routing and lifecycle.
- `src/amberclaw/heartbeat/`: Continuous async process monitoring.
- `src/amberclaw/memory/`: 3-layer RAG and session persistence.
- `src/amberclaw/security/`: Sandboxing and egress controllers.
- `src/amberclaw/governance/`: Auto-budget limits and approval boards.
