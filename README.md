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
- **ClawHardware Integration**: Native support for **Raspberry Pi GPIO**, and serial communication with **Arduino/ESP32** peripherals.

## Hardware & Edge Support

AmberClaw is designed to run as the primary AI OS on edge devices.

### 🍓 Raspberry Pi (ClawOS)
To turn your RPi into an autonomous AI node:
```bash
./scripts/setup_rpi.sh
```
This script installs dependencies, optimizes the Python environment for ARM, and sets up AmberClaw as a systemd service.

### 🔌 Microcontrollers (Arduino/ESP32)
AmberClaw can control peripheral hardware nodes via Serial. 
1. Flash your device with the provided firmware: `examples/hardware/amber_node.ino`.
2. Connect via USB.
3. Use the `hardware_send_command` or `hardware_read_sensor` tools to interact with your physical environment.

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
