# AmberClaw AI OS: Master Unified Tracker & Implementation Roadmap

> **System Prompt Directive for AI Models:**
> This file is the single, definitive source of truth for the AmberClaw project. AmberClaw is an Autonomous AI OS Kernel designed for high-risk enterprise workloads, edge sovereignty, and extreme security. 
> 
> **Instructions for AI Coding Assistants:**
> 1. When working on any task, read this tracker first to locate the feature under development.
> 2. Do not start a task unless its preceding dependencies (marked `[EXISTING]` or checked off) are complete.
> 3. Update the state indicators in this file once you finish a task:
>    - Change `[ ]` to `[x]` and add a brief commit hash or timestamp.
> 4. Ensure all code modifications adhere strictly to the zero-trust isolation and dependency injection patterns outlined in `codebase_context.md`.

---

## 1. Core Architecture & OS Kernel
- [x] **ClawOSSupervisor**: Manages complete async startup/teardown lifecycles.
- [x] **MessageBus**: Event-driven async routing for inter-service communication.
- [x] **Dependency Injection Container**: Decouples modules across the 40+ packages.
- [x] **Pydantic V2 Configuration**: Schema validation with YAML backend.
- [x] **Out-of-Process Plugin Host**: Implement `amberclaw/plugins/host.py` using subprocesses or RPC channels to run third-party extensions in separate, capability-restricted hosts.
- [x] **Plugin Registry & Manifest**: Create `amberclaw/plugins/registry.py` and `manager.py` to auto-discover, load, and validate extensions using a standard `plugin.yaml` manifest format (allowing third-party tools to auto-register).
- [x] **PostgreSQL & Redis State Migration**: Move storage and state management from local SQLite/JSON databases to distributed PostgreSQL (multi-tenancy) and Redis (pub/sub and caching for scaling multi-instance deployments). [Completed: 2026-06-02]
- [x] **Model Capability Detection**: Implement dynamic model capability detection to automatically route tasks based on the LLM's context window, reasoning capability, and vision support. [Completed: 2026-06-02]
- [x] **Prompt Caching Support**: Extend CLI/SDK routing to support Anthropic / OpenAI prompt caching headers dynamically to optimize costs. [Completed: 2026-06-02]
- [x] **JSON Mode Enforcement**: Enforce json-mode or structured tool call modes in the LLM router to prevent unstructured text outputs when structured formats are expected. [Completed: 2026-06-02]
- [x] **Quantization & Speculative Decoding**: Add config options and runner support for quantized local models (GGUF, AWQ) and speculative decoding setups. [Completed: 2026-06-03]

---

## 2. Advanced Memory System (3-Layer & Dialectic)
- [x] **Mem0 User Memory**: Basic user profile and conversational knowledge tracking.
- [x] **ChromaDB Vector Store**: Vector database for document chunk retrieval.
- [x] **Hybrid Search Pipeline**: Add disk persistence to the BM25 keyword index and combine with vector search + cross-encoder reranking. [Completed: 2026-06-03]
- [x] **Frozen-Snapshot Persistent Memory**: Create `amberclaw/memory/frozen_memory.py` managing `MEMORY.md` (facts, preferences) and `USER.md` (profile) as immutable prompt injection blocks read once at start to preserve prefix caches. [Completed: 2026-06-03]
- [x] **SQLite Session Database (WAL + FTS5)**: Create `amberclaw/memory/session_db.py` to store complete conversation turns, supporting SQLite virtual tables for full-text conversational search and transaction logging. [Completed: 2026-06-03]
- [x] **Memory Manager Orchestration**: Implement `amberclaw/memory/manager.py` with recall modes: `hybrid` (vector + search + Honcho), `context` (automatic turn injection), or `tools` (agent-triggered search/retrieval). Support write frequencies: `async`, `turn`, `session`, or `N` turns. [Completed: 2026-06-03]
- [x] **Honcho Dialectic User Modeling**: Implement `amberclaw/memory/honcho_provider.py` to integrate with Honcho API. Support separate user/AI peer representations, observe toggles (`observeMe`, `observeOthers`), mutual observation modes (`directional` vs `unified`), and three sequential reasoning passes: *Initial Assessment* -> *Self-Audit* -> *Reconciliation*. [Completed: 2026-06-03]
- [x] **Temporal Graph Memory**: Implement vector + knowledge graph hybrids (integrating Mem0g, Zep/Graphiti, or Cognee) to track time-aware fact changes and multi-hop entity relationships over time. [Completed: 2026-06-03]
- [x] **Memory Agent Tools**: Implement `amberclaw/tools/memory_tools.py` registering `remember`, `recall`, `forget`, `session_search`, and `summarize_session` tools. [Completed: 2026-06-03]
- [x] **Multi-Scope Memory**: Partition memory access into distinct scopes: `user`, `agent`, `session`, and `organization` tiers. [Completed: 2026-06-03]
- [x] **Multi-Source Ingestion**: Build ingestion pipelines for files, web pages, and messages to load directly into the RAG memory. [Completed: 2026-06-03]
- [x] **RAGAS Evaluation Integration**: Implement evaluation harnesses using RAGAS to monitor retrieval accuracy, faithfulness, and answer relevance. [Completed: 2026-06-03]

---

## 3. Autonomous Intelligence, Planning & Learning Loop
- [x] **LiteLLM Router**: Abstraction layer for LLM routing.
- [x] **LangGraph Engine**: Stateful graph-based loop execution.
- [x] **Execution Modes**: Simple ReAct, Plan-and-Execute, and basic routing.
- [x] **Plan-Execute-Reflect Loop**: Modernize agent architecture. Add an explicit reasoning-reflection module (`amberclaw/agent/learning_loop.py`) where agents evaluate their own outputs and self-correct on failures. [Completed: 2026-06-04]
- [x] **Autonomous Skill Creator (`SkillCreator`)**: Monitor tool use trajectories. When a task takes >3 turns or >5 tool calls, automatically synthesize a structured Markdown skill document (with steps, known facts, and verification) and save it to `~/.amberclaw/skills/auto-created/[skill].md`. [Completed: 2026-06-04]
- [x] **Skill Self-Improver (`SkillImprover`)**: Track skill success/failure rates. If a skill's success rate falls below 50%, trigger auto-refinement (adding error handling, adjusting constraints). Expose a `skill_manage` tool to let the agent edit, merge, or delete its own skills. [Completed: 2026-06-04]
- [x] **Memory Nudge System (`MemoryNudgeSystem`)**: Implement proactive agent self-prompting (session-end, pattern-detected, periodic every 10 turns) to identify key user facts and preferences to persist long-term. [Completed: 2026-06-04]
- [x] **A2A (Agent-to-Agent) Collaboration**: Add Agent-to-Agent protocol support based on JSON-RPC 2.0 to allow AmberClaw instances to delegate tasks to other local/remote agents. [Completed: 2026-06-04]
- [x] **Hierarchical Agent Orchestration**: Support a root coordinator agent routing sub-tasks to specialized worker agents with different tool access. [Completed: 2026-06-04]
- [x] **Computer Use / GUI Agent**: Integrate OSWorld-like GUI interaction capabilities to allow keyboard/mouse control in sandboxed desktops. [Completed: 2026-06-04]

---

## 4. Zero-Trust Security Stack & Sandbox Execution
- [x] **Landlock LSM Filesystem Sandbox**: Kernel-level path isolation (Linux 5.13+).
- [x] **Egress Firewall**: Socket monkey-patching for task-level network isolation.
- [x] **Fernet Secret Vault**: Encrypted credential storage with proxy resolution.
- [x] **Cryptographic Audit Log**: Tamper-evident, SHA-256 hash-chained JSONL logging.
- [x] **YAML Security Blueprints**: Posture profiles (Paranoid, Dev, Minimal).
- [x] **PII Redaction Engine**: Upgrade basic regex scrubbers to Microsoft Presidio for advanced NER-based detection of PII/PHI in prompt inputs and outputs. [Completed: 2026-06-04]
- [x] **Human-in-the-Loop (HITL) Board**: Wire existing risk assessment logic to TUI and Web interfaces for operator approval before high-risk actions. [Completed: 2026-06-04]
- [x] **Security Sandbox Core (Landlock + seccomp)**: Implement `amberclaw/security/sandbox.py` using Landlock LSM (isolate workspace/tmp), seccomp-bpf filters (block `execve`, `ptrace`), namespaces (`unshare`), capability dropping (`cap-drop ALL`), non-root execution (`sandbox` user), and process limit controls. [Completed: 2026-06-03]
- [x] **SSRF & TLS Egress Guard**: Refactor network security to enforce SSRF validation, TLS-only endpoints, and per-binary restriction (e.g., git can only hit GitHub, python only PyPI). [Completed: 2026-06-04]
- [x] **WhatsApp Bridge Security Audit**: Completed audit and sandboxed Node.js bridge runtime using bubblewrap (bwrap) namespaces, path traversal fixes, CSWSH protections, and constant-time token validation. [Completed: 2026-06-04]
- [ ] **Container Isolation Validation**: Add automated checks to ensure running container backends enforce read-only roots, drop capabilities, and prevent privilege escalation.
- [ ] **DM Pairing (`/pair`)**: Implement secure verification code flow for messaging platforms to pair user IDs with access permissions.
- [ ] **RBAC (Role-Based Access Control)**: Enforce role permissions checking user IDs against permission maps for tool execution.
- [ ] **Secret Scanning**: Implement scan checks on workspace files before committing or exporting trajectories to ensure no API keys are exposed.

---

## 5. Terminal & Execution Backends (6+ Backends)
- [x] **Local Backend**: `subprocess.run()` command execution.
- [x] **Docker Backend**: Isolated container execution using docker CLI / asyncio subprocesses with namespaces, read-only root, cap drops, and resource caps. [Completed: 2026-06-03]
- [ ] **SSH Backend**: Remote system execution via `paramiko` supporting agent forwarding and reconnection.
- [ ] **Daytona Backend**: Managed serverless dev environments that hibernate when idle and wake on demand.
- [ ] **Singularity / Apptainer Backend**: Containerized execution for HPC clusters without Docker daemon, running `singularity exec --containall --no-home`.
- [ ] **Modal Backend**: Ephemeral cloud sandboxes with container filesystem persistence across recreations.
- [ ] **Vercel Sandbox Backend**: MicroVM isolation with fast cold starts and snapshot-backed filesystems.
- [ ] **Backend Factory**: Implement `BackendFactory` at `amberclaw/terminal/factory.py` to dynamically instantiate and validate backends from configuration.

---

## 6. Voice Mode & Multimodal I/O
- [ ] **Voice Mode Base**: Implement interruptible microphone loops, voice activity detection (VAD), and real-time audio input streaming (`amberclaw/voice/base.py`).
- [ ] **Premium TTS**: Integrate ElevenLabs streaming text-to-speech engine.
- [ ] **Local TTS Fallback**: Implement `NeuTTS` provider using a local neural speech synthesizer for offline operation.
- [ ] **Speech Recognition (STT)**: Integrate speech-to-text supporting Whisper (local/API) and Google STT.
- [ ] **Platform Voice Handlers**: Wire voice capabilities into Discord bots (voice channel client) and Telegram bots (transcribe audio messages, reply with voice assets).
- [ ] **Multimodal Vision & Video**: Add support for parsing image files/video frames across all channels (Telegram, Discord) and routing them to vision-capable backends.

---

## 7. Reinforcement Learning (RL) Pipeline
- [ ] **RL Trainer Core**: Create `amberclaw/rl/trainer.py` to run GRPO (Group Relative Policy Optimization) with LoRA adapters using the Tinker-Atropos framework.
- [ ] **Three-Process Orchestration**: Automate startup of Atropos API server, Tinker trainer (with SGLang inference on port 8001), and Environment server with staggered delays (5s, 30s, 90s).
- [ ] **Trajectory Management**: Implement `amberclaw/rl/trajectory.py` to save trajectories (JSONL), batch export, and compress sequences using a "head-tail protection, middle summarization" algorithm.
- [ ] **Environment Definitions**: Define RL environments for `tool_use`, `code_gen`, `reasoning`, and `conversation`.
- [ ] **WandB Logging**: Track rewards (`reward_mean`, `reward_std`), training loss, and target evaluations on weights.
- [ ] **RL Tools**: Implement tools for agent interaction: `rl_list_environments`, `rl_select_environment`, `rl_start_training`, `rl_stop_training`, `rl_check_status`, and `rl_test_inference`.
- [ ] **System Verification**: Create `amberclaw/rl/system_check.py` to verify Py 3.11+, GPU, VRAM (24GB+ for 4090/A100), and library dependencies.

---

## 8. Interfaces (TUI & Web Dashboard)
- [ ] **Textual Rich TUI**: Implement `amberclaw/tui/app.py` providing a split-pane layout (left: chat markdown, right: streaming logs and tool output) with multiline syntax highlighted input.
- [ ] **TUI Slash Commands**: Add autocomplete for `/model`, `/skills`, `/compress`, `/usage`, `/insights`, `/personality`, `/reset`, and `/stop`.
- [ ] **FastAPI Web Dashboard**: Implement a FastAPI REST server with SSE streaming endpoints for chat.
- [ ] **SPA Frontend**: Build a responsive browser UI (Gradio, React, or static HTML/JS) exposing chat, configuration, session history, memory browsing, and skill installations.
- [ ] **Dashboard Authentication**: Implement token-based auth and CORS configurations for secure dashboard access.

---

## 9. Subagents, Parallel Delegation & RPC
- [ ] **SubAgent Class**: Implement `amberclaw/subagent/agent.py` creating isolated subagent processes with independent conversation histories, tool subsets, and terminal backends.
- [ ] **SubAgent Pool**: Implement `amberclaw/subagent/pool.py` to spawn and orchestrate multiple subagents executing tasks in parallel/sequential batches.
- [ ] **Programmatic Tool Calling (RPC)**: Create `amberclaw/subagent/rpc.py` to provide a `ToolRPC` interface. Allows subagent Python scripts to call parent tools, collapsing multi-step workflows into a single inference turn.
- [ ] **Context Isolation**: Implement a context isolator using `contextvars` to prevent subagent state leaks.
- [ ] **Subagent Control Tools**: Register `spawn_subagent`, `delegate_to_subagent`, `list_subagents`, and `terminate_subagent`.

---

## 10. Context, Prompt & Personality Management
- [ ] **Context Compression**: Implement `amberclaw/agent/compression.py` utilizing LLM-based summarization and pruning of tool logs to compress conversation logs when near the token limit.
- [ ] **Usage Insights**: Track cost and token consumption per session, provider, and model inside SQLite; expose `/usage` and `/insights` commands.
- [ ] **Project Context Files**: Add auto-loading of `.amberclaw.md` or `AGENTS.md` context files when executing commands in target directories.
- [ ] **Personality System**: Implement `amberclaw/agent/personality.py` allowing custom agent behaviors, voices, and values defined in `SOUL.md` (with `/personality` runtime switching).

---

## 11. Tooling & Skills Ecosystem (ClawHub, 68+ Tools)
- [ ] **Tool Registry**: Refactor to a dynamic, self-registering `@tool` decorator discovery system that registers tools without central lists.
- [ ] **Progressive Disclosure**: Load only lightweight skill descriptions (50 tokens) during initial prompts, fetching full implementations only when semantically matched or invoked.
- [ ] **Curated Toolsets**: Group tools into `core`, `coding`, `research`, `creative`, and `system` sets, allowing admins to enable/disable entire packages.
- [ ] **Built-in Web Control Tools**: Add native `web_search` (Tavily/Brave/SerpAPI), `web_extract` (HTML-to-markdown), `web_browse` (interactive browser), and image/TTS generation tools that do not require external MCP servers.
- [ ] **Skills Hub Integration**: Implement `amberclaw/skills/hub.py` to discover, install, and uninstall skills from remote registries across 17 categories (macOS, coding-delegation, research-tools, etc.).
- [ ] **Skill Safety Scanner**: Implement `amberclaw/skills/scanner.py` to parse downloaded skills for dangerous imports (ctypes, socket), obfuscated scripts, hardcoded secrets, and out-of-workspace file writes.
- [ ] **AgentSkills Standard**: Support import/export formats matching the `agentskills.io` standard spec.

---

## 12. Messaging Platform Integrations (15+ Platforms)
- [x] **Base Channels**: Telegram, Discord, WhatsApp, Slack, Feishu, DingTalk, Email, QQ, Matrix, Mochat.
- [x] **MCP / A2A Support**: Fully compatible with MCP 2026 spec and agent-to-agent JSON-RPC.
- [ ] **Expanded Channels**: Add Signal (via signal-cli), Mattermost (WebSocket), Twilio SMS (with MMS support), WeChat (WeChaty), BlueBubbles (iMessage on macOS), and Home Assistant (webhooks/service calls).
- [ ] **Conversation Continuity**: Implement `amberclaw/channels/continuity.py` using session IDs to hand off active agent tasks smoothly from one channel (e.g., CLI) to another (e.g., mobile Telegram).

---

## 13. Scheduling & Automation (Cron)
- [ ] **Natural Language Cron**: Implement `amberclaw/cron/nlp.py` to convert natural language statements ("every Monday at noon") into valid crontab configurations.
- [ ] **Platform Delivery Routing**: Configure scheduled task outputs to deliver directly to specific Telegram chats, Discord channels, Slack threads, or Emails.
- [ ] **Task Management UI & Logs**: Create interactive CLI/Web systems to view active cron jobs, execution logs, and run-times.

---

## 14. Installation, Deployment & CI/CD Operations
- [x] **Docker Ecosystem**: Standard Dockerfile, compose files, and secure presets.
- [x] **Systemd Setup**: Edge/RPi automatic setup scripts.
- [ ] **Hardened Multi-Stage Dockerfile**: Rewrite `Dockerfile` using multi-stage builds (`python:3.11-slim` builder to distroless/alpine runtime), non-root `sandbox` user, dropped capabilities, and read-only roots. Include custom seccomp profiles.
- [ ] **Docker Gateway Isolation**: Create a separate `Dockerfile.gateway` that only installs core and channel adapters, avoiding heavy machine learning and sandbox dependencies.
- [ ] **One-Line Installer**: Build `scripts/install.sh` to auto-detect environments (Linux, macOS, WSL2, Termux), set up Python/uv/venv, create `~/.amberclaw/`, and install with appropriate platform extras (`.[termux]` for voice-free, `.[macos]`).
- [ ] **Migration Tool**: Create `amberclaw/cli/migrate.py` to migrate personas, memories, skills, and configuration files from other open-source frameworks (e.g., OpenClaw).
- [ ] **Doctor Diagnosis Command**: Implement `amberclaw doctor` to check GPU configurations, dependencies, API reachability, database locks, and output repair suggestions.
- [ ] **CI/CD Pipelines**: Set up GitHub workflows for:
  - Security scanning (Bandit, Gitleaks, Trivy image scans).
  - PyPI auto-publishing on tagged releases.
  - Automated Docker multi-arch builds (amd64, arm64) pushed to GitHub Container Registry (GHCR).

---

## 15. Model Providers & API Integrations
- [ ] **Default Models Update**: Fix default non-existent `anthropic/claude-opus-4-5` to SOTA models (`claude-3-5-sonnet`, `claude-4-opus`, `gpt-4o`, `gemini-1.5-pro`).
- [ ] **New Providers**: Support Nous Portal, NVIDIA NIM, Xiaomi MiMo, z.ai/GLM, Kimi/Moonshot, MiniMax, Amazon Bedrock, and Hugging Face Inference API.
- [ ] **Inference Routing & Credential Proxy**: Create `amberclaw/inference/router.py` and `proxy.py` routing all LLM calls through a local proxy. Encrypt credentials in `~/.AmberClaw/credentials/` using Fernet (master key from env); proxy injects keys so agents never see raw credentials.
- [ ] **OAuth Login Flow**: Add CLI oauth client for headless verification of provider tokens.

---

## 16. Agent Client Protocol (ACP) & IDEs
- [ ] **ACP Server**: Implement `amberclaw/acp/server.py` supporting Agent Client Protocol (JSON-RPC 2.0 endpoints for list tools, call tool, list prompts) for external IDE adapters.
- [ ] **Editor Plugins**: Support VS Code, Cursor, Windsurf, and Zed integrations.

---

## 17. Repository Metadata, Discoverability & Housekeeping
- [ ] **GitHub Description**: Add descriptive tagline: "Lightweight personal AI assistant framework — any LLM, any chat platform, 4k lines of Python".
- [ ] **GitHub Topics**: Set repo topics: `ai-agent`, `llm`, `mcp`, `multi-agent`, `personal-assistant`, `python`, `telegram-bot`.
- [ ] **GitHub Website Link**: Set repository website link to public documentation or github pages.
- [ ] **Publish Releases**: Tag official release `v0.1.0` and compile detailed CHANGELOG notes.
- [ ] **GitHub Social Preview**: Create and attach a 1280x640px repository social card image.
- [ ] **Issue & PR Templates**: Add `.github/ISSUE_TEMPLATE/` (bug_report.md, feature_request.md) and `.github/pull_request_template.md`.
- [ ] **funding.yml**: Add `.github/funding.yml` for donation/sponsorship platforms.
- [ ] **Demo Media**: Record and insert high-quality screen capture GIFs/videos showing AmberClaw in action.
- [ ] **GitHub Discussion Categories**: Initialize discussion categories on GitHub.
- [ ] **License Year & Badges**: Update license copyrights and include PyPI, build, coverage, and license badges in README.md.
- [ ] **Broken Links Check**: Scan README and docs for dead URLs.

---

## 18. Documentation, LLMs.txt & Learning Paths
- [ ] **llms.txt Generator**: Build `amberclaw/docs/llms_txt.py` to auto-generate a 17KB machine-readable documentation index.
- [ ] **llms-full.txt Generator**: Build `amberclaw/docs/llms_full.py` to generate a 1.8MB full one-shot context dump of all repo document files.
- [ ] **Dedicated Documentation Site**: Set up MkDocs/Mintlify document trees detailing architecture, deployment, and skill authoring guides.
- [ ] **API Reference Site**: Generate reference pages from code annotations.
- [ ] **Troubleshooting & FAQ Guide**: Include common errors (db locks, driver issues).
- [ ] **Alternatives Comparison Page**: Document how AmberClaw compares to competing agent frameworks.
- [ ] **Example Configuration Templates**: Provide `config.yaml.example` profiles.
- [ ] **Windows OS Installation Guide**: Document installation and setup on native Windows environments.

---

## 19. Skin Engine & Themability
- [ ] **TUI / Web Theming**: Create a modular skin system (`default` dark, `light`, `high-contrast`, `ocean`, `forest`) mapped as data tokens for text colors, borders, and panel styling.

---
*Master Tracker Consolidated. Awaiting sequential execution of missing components.*
