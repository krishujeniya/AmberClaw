# Minimal Runtime and Optional-Package Split Plan (CL-002 / Observation A11)

## Executive Summary

Observation A11 identifies that `pyproject.toml` currently bundles scientific/data libraries (`pandas`, `matplotlib`, `seaborn`, `openpyxl`, `h2o`), channel adapters (`python-telegram-bot`, `matrix-nio`, `slack-sdk`, `google-api-python-client`), and storage drivers (`chromadb`, `mem0ai`, `asyncpg`, `redis`) directly in the base `dependencies` list. Only execution sandboxes are split into optional extras.

This plan specifies the architecture to modularize AmberClaw into a lean base runtime with optional feature extras, targeting minimal cold-start latency, reduced container image size, and a dramatically minimized dependency attack surface.

---

## Baseline Dependency Footprint

- **Total installed packages**: 315 packages in virtual environment.
- **Base dependencies in `pyproject.toml`**: 52 packages.
- **Current container / wheel size**: ~1.8GB virtual environment, 490 source modules.
- **Identified advisory surface**: 45 advisories across 13 packages, of which 40 advisories reside in optional/ecosystem modules (`chromadb`, `h2o`, `filelock`, `langchain*`).

---

## Target Package Profiles

### 1. `amberclaw` (Core Base Runtime)
Minimal footprint for CLI, REST/SSE gateway, SQLite session persistence, and local kernel containment.
- **API & Web**: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `httpx`, `python-multipart`, `passlib[bcrypt]`, `pyjwt[crypto]`, `authlib`, `python3-saml`
- **CLI & TUI**: `typer`, `rich`, `textual`
- **Core Agent & Bus**: `litellm`, `json-repair`, `loguru`, `python-dotenv`, `pyyaml`
- **Persistence**: `sqlalchemy`, `aiosqlite`, `alembic`, `greenlet` (SQLite FTS5)
- **Observability & Security**: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `prometheus-client`, `croniter`
- **Containment**: Built-in Linux Landlock and seccomp syscall filters.

### 2. `amberclaw[data]` (Autonomous Data Science Team)
Optional scientific and machine learning dependencies used exclusively in `src/amberclaw/data/`:
- `pandas>=2.2.0`
- `matplotlib>=3.8.0`
- `seaborn>=0.13.0`
- `openpyxl>=3.1.0`
- `h2o>=3.44.0`
- `ipython>=8.20.0`

### 3. `amberclaw[channels]` (External Messaging Transport Adapters)
Optional protocol adapters for external chat and messaging platforms:
- `python-telegram-bot>=22.7`
- `matrix-nio>=0.20.0`
- `slack-sdk>=3.27.0`
- `slackify-markdown>=0.1.0`
- `google-api-python-client>=2.0.0`
- `google-auth-oauthlib>=1.0.0`
- `oauth-cli-kit>=0.1.0`
- `pyserial>=3.5`

### 4. `amberclaw[storage]` (Enterprise Vector and Distributed Stores)
Optional vector databases and multi-node caching/storage backends:
- `chromadb>=0.4.22`
- `mem0ai>=2.0.1`
- `asyncpg>=0.29.0`
- `redis>=5.0.0`
- `paramiko>=3.4.0`

### 5. `amberclaw[sandboxes]` (Managed & Cloud Execution Environments)
Retains existing optional sandbox drivers:
- `daytona>=0.184.0`
- `modal>=0.63.0`
- `vercel>=0.5.9`
- `wasmtime>=20.0.0`
- `micropython-wasm>=0.1a2`
- `e2b>=1.0.0`

### 6. `amberclaw[all]`
Meta-extra installing all optional components for development environments and full integration CI testing.

---

## Code Guardrails and Dynamic Imports

To support unbundled installations without runtime crashes:
1. Every optional subsystem must implement import guards following the pattern:
   ```python
   try:
       import h2o
       from h2o.automl import H2OAutoML
       HAS_H2O = True
   except ImportError:
       HAS_H2O = False
   ```
2. Dynamic feature checks must raise an actionable `FeatureNotInstalledError`:
   `"The data science module requires amberclaw[data]. Install it via: pip install 'amberclaw[data]'"`
3. Unit tests must use `pytest.importorskip()` for optional dependencies when running against a minimal base install.

---

## Migration and Verification Sequence

1. **Phase 0 (CL-002 - Completed)**: Document dependency inventory, advisory reachability matrix, and packaging split plan. Refresh SBOM.
2. **Phase 2 (CL-016 - Scheduled)**:
   - Split `[project.dependencies]` in `pyproject.toml` into `[project.optional-dependencies]`.
   - Add dynamic import guards across `src/amberclaw/data/` and `src/amberclaw/channels/`.
   - Update Dockerfile to build dual target images: `amberclaw:minimal` and `amberclaw:full`.
   - Measure cold start and idle memory RSS reduction using `benchmarks/benchmark_suite.py`.
