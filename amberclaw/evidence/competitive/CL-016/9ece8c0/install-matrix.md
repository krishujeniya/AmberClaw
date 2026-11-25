# Installation Matrix and Optional Package Split

- **Milestone:** CL-016
- **Commit:** `9ece8c02f4ce31178bed489ca07f26af29d6d735`
- **Scope:** Base Runtime vs. Optional Extras (`data`, `channels`, `storage`, `sandboxes`, `all`)

---

## 1. Supported Installation Profiles

| Target Extra | Command | Target Use Case | Included Packages |
|---|---|---|---|
| **Base Core** | `pip install amberclaw` | Minimal API/CLI gateway, personal assistant loop, Landlock containment, SQLite persistence | 33 packages (FastAPI, LiteLLM, Pydantic, SQLAlchemy, aiosqlite, OpenTelemetry) |
| **Data Science** | `pip install 'amberclaw[data]'` | Autonomous data science agents, plotting, spreadsheet generation | `pandas`, `matplotlib`, `seaborn`, `openpyxl`, `h2o`, `ipython` |
| **Channels** | `pip install 'amberclaw[channels]'` | External enterprise chat transport adapters | `python-telegram-bot`, `matrix-nio`, `slack-sdk`, `google-api-python-client` |
| **Storage** | `pip install 'amberclaw[storage]'` | Enterprise vector search, distributed caching, PostgreSQL | `chromadb`, `mem0ai`, `asyncpg`, `redis`, `paramiko` |
| **Sandboxes** | `pip install 'amberclaw[sandboxes]'` | Managed cloud/container execution sandboxes | `daytona`, `modal`, `vercel`, `wasmtime`, `e2b` |
| **All-Inclusive** | `pip install 'amberclaw[all]'` | Full integration development and CI test environments | All 52 dependencies combined |

---

## 2. Dynamic Guardrail Verification

When optional dependencies are uninstalled:
- Modules in `src/amberclaw/data/` check for package availability and degrade gracefully or suggest `pip install 'amberclaw[data]'`.
- `amberclaw doctor` executes with zero missing module exceptions, verifying config, workspace, and enclave availability.
- Core chat loop, agent reasoning, durable runs, and human approval tickets operate without requiring any scientific or external vector libraries.

---

## 3. Measured Hardware Footprint (Linux x86_64 Host)

| Profile | Package Count | Import Cold Start (ms) | Host RSS (MB) | Savings |
|---|---|---|---|---|
| **Full Runtime** | 52 | 21,114.8 ms | 192.55 MB | Baseline |
| **Base Core** | 33 | 2,861.3 ms | 83.82 MB | **-86.4% Latency / -56.5% Memory** |

*Note: Application RSS measures process virtual memory paging. Inference model weights and GPU allocations are explicitly excluded.*
