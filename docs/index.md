# AmberClaw AI OS

> **The open, self-hosted, zero-trust agent runtime for teams and individuals who need private, auditable AI automation across models, tools, and communication channels.**

---

## 🏛️ Core Pillars

1. **Secure by Construction** — Every agent action is authenticated, authorized, isolated via Linux Landlock or container micro-sandboxes, budgeted, and audited with SHA-256 hash chains.
2. **Runs Anywhere** — Seamless execution across local machines, servers, cloud developer environments, edge devices, and serverless backends.
3. **Any Model, Consistent Behavior** — Capability-aware LLM routing via LiteLLM supporting OpenAI, Anthropic, Ollama, vLLM, and local models.
4. **Persistent and Useful Memory** — SQLite SessionDB FTS5 full-text indexing, multi-scope memory management, and verifiable GDPR right-to-be-forgotten deletion.
5. **Action Transparency** — Structured JSONL audit trails, approval boards for high-risk actions, and Prometheus metrics for full operational visibility.
6. **Instant Activation** — Quick onboarding wizard (`amberclaw onboard`), built-in diagnostic doctor (`amberclaw doctor`), and zero-setup web dashboard.

---

## 🚀 Getting Started

To get started with AmberClaw:

1. **[Quickstart & Setup](setup.md)**: Install dependencies with `uv`, configure your environment, and run initial diagnostics.
2. **[Zero-Trust Architecture](architecture.md)**: Explore the decoupled asynchronous message bus, Landlock LSM containment, and 9 execution sandboxes.
3. **[API Reference](api.md)**: Inspect REST endpoints, SSE streaming protocols, authentication headers, and Prometheus telemetry.
4. **[Building Agent Skills](skills.md)**: Create modular tools and skills with strict Pydantic schema validation.

---

## ⚡ Execution Sandboxes

AmberClaw provides 9 interchangeable execution backends:

- **Local**: Subprocess workspace containment with Landlock LSM.
- **Docker**: Isolated containerized process isolation.
- **SSH**: Remote shell execution over secure SSH tunnels.
- **Daytona**: Developer workspace cloud sandboxing.
- **Singularity / Apptainer**: HPC container execution.
- **Modal**: Ephemeral serverless container runtime.
- **Vercel**: Serverless micro-VM code execution.
- **WASM (Wasmtime)**: Fuel-bounded WebAssembly micro-runtime.
- **E2B**: Firecracker microVM isolated sandboxing.
