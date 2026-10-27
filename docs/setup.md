# Installation & Setup Guide

This guide walks you through setting up and verifying your AmberClaw AI OS environment.

---

## 📋 Prerequisites

- **Python**: 3.11 or higher
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- **Operating System**: Linux (recommended for Landlock LSM), macOS, or Windows (WSL2)

---

## 🛠️ Step 1: Clone and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/krishujeniya/AmberClaw.git
cd AmberClaw

# Copy the example environment file
cp .env.example .env

# Install dependencies using uv
uv sync
```

---

## ⚙️ Step 2: Environment Configuration

Edit `.env` to configure your LLM providers and secrets:

```ini
# Core Configuration
AMBERCLAW_ENV=development
AMBERCLAW_WORKSPACE_DIR=./data/workspace
AMBERCLAW_SECRET_KEY=your-32-byte-secret-key

# LLM Providers (Configure at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_API_BASE=http://localhost:11434

# Security Controls
AMBERCLAW_AUTH_ENABLED=true
AMBERCLAW_RATE_LIMIT=10
```

---

## 🩺 Step 3: Run System Diagnostics (`doctor`)

AmberClaw includes an automated doctor command that verifies configuration paths, provider keys, sandbox dependencies, and permissions:

```bash
uv run amberclaw doctor
```

Output highlights verified subsystems:
- ✅ Config file valid
- ✅ Workspace directory writable
- ✅ Provider keys detected
- ✅ Execution backend dependencies ready

---

## 🚀 Step 4: Launch AmberClaw

### Option A: Interactive CLI Mode
```bash
uv run amberclaw agent
```

### Option B: FastAPI Gateway & Web Dashboard
```bash
uv run uvicorn amberclaw.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Navigate to `http://localhost:8000` to access the Web Dashboard SPA.

### Option C: Guided Onboarding Wizard
```bash
uv run amberclaw onboard
```

---

## 🔒 Step 5: Containerized & Air-Gapped Deployments

### Hardened Multi-Container Production Stack
```bash
docker compose -f deploy/docker/docker-compose.prod.yml up -d
```

### 100% Air-Gapped / Zero-Egress Offline Stack
For strictly air-gapped environments with no outbound internet access, run the local inference stack powered by embedded Ollama and ChromaDB:

```bash
docker compose -f deploy/docker/docker-compose.airgapped.yml up -d
```
All communication is confined to an internal isolated bridge (`internal: true`) without external internet routing.
