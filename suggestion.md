

1. REPOSITORY METADATA & DISCOVERABILITY

AC-001 | Populate GitHub Repository About Section
- Priority: P1 | Scope: Repository | Sources: C-A1, C-A2, C-A3, G
- Description: Add a one-line description ("Lightweight personal AI assistant framework — any LLM, any chat platform, 4k lines of Python"), relevant topics (`ai-agent`, `llm`, `mcp`, `multi-agent`, `personal-assistant`, `python`, `telegram-bot`), and a website URL (PyPI or docs).
- Acceptance: GitHub About section is 100% populated; repository appears in targeted GitHub searches.

AC-002 | Publish GitHub Releases with Semantic Versioning
- Priority: P1 | Scope: Repository | Sources: C-A4, G
- Description: Create initial release (e.g., `v0.1.0` or `v1.0.0`) with proper git tags, release notes, and changelog. Currently zero releases exist despite CHANGELOG having a `1.0.0` entry.
- Acceptance: At least one official GitHub Release is published with attached artifacts and conventional changelog.

AC-003 | Add Social Preview / OpenGraph Image
- Priority: P2 | Scope: Repository | Sources: C-A5
- Description: Upload a 1280×640px custom OG image showing the AmberClaw logo and tagline for social sharing.
- Acceptance: Sharing the repo on Twitter/LinkedIn/Discord renders a custom card.

AC-004 | Add Standard GitHub Badges to README
- Priority: P2 | Scope: Repository | Sources: C-A9, G
- Description: Add badges for PyPI version, Docker pulls, CI status, test coverage, license, and last commit to the top of README.md.
- Acceptance: README header contains ≥6 working badges.

AC-005 | Add GitHub Issue Templates
- Priority: P2 | Scope: Repository | Sources: C-A6, G, M
- Description: Create `.github/ISSUE_TEMPLATE/` with bug report, feature request, and skill request forms.
- Acceptance: New issues present a structured form instead of a blank text box.

AC-006 | Add GitHub Pull Request Template
- Priority: P2 | Scope: Repository | Sources: C-A7, G
- Description: Add `.github/PULL_REQUEST_TEMPLATE.md` with checklist for tests, docs, security, and change type.
- Acceptance: Every new PR auto-populates with the template.

AC-007 | Add FUNDING.yml for Community Support
- Priority: P3 | Scope: Repository | Sources: C-A8
- Description: Add `.github/FUNDING.yml` linking to GitHub Sponsors, Buy Me a Coffee, or similar.
- Acceptance: Sponsor button appears on repository page.

AC-008 | Add Demo GIF or Video to README
- Priority: P1 | Scope: Documentation | Sources: C-A9, G
- Description: Record a 30–60 second screen capture showing AmberClaw responding to messages across Telegram/Discord and executing a tool. Embed in README.
- Acceptance: README contains a visible demo media file (GIF/MP4) above the fold.

AC-009 | Configure GitHub Discussions Categories
- Priority: P3 | Scope: Repository | Sources: C-A10
- Description: Set up GitHub Discussions with categories: Q&A, Ideas, Show & Tell, and General.
- Acceptance: Discussions tab is active with ≥4 configured categories.

AC-010 | Add CODEOWNERS and CITATION Files
- Priority: P3 | Scope: Repository | Sources: G
- Description: Add `CODEOWNERS` for review routing and `CITATION.cff` (or `CITATION.md`) for academic attribution.
- Acceptance: Both files exist in repository root.

---

2. PROJECT CONFIGURATION, PACKAGING & DISTRIBUTION

AC-011 | Fix Package Name Inconsistency
- Priority: P0 | Scope: Packaging | Sources: C-B11, G
- Description: Resolve mismatch between `name = "amberclaw"` in pyproject.toml, PyPI badge linking to `amberclaw-ai`, and install command `pip install amberclaw-ai`. Unify to one canonical name.
- Acceptance: `pip install <canonical-name>` and `import amberclaw` work identically; no naming confusion remains.

AC-012 | Add Project URLs to pyproject.toml
- Priority: P1 | Scope: Packaging | Sources: C-B12, G
- Description: Populate `[project.urls]` with Homepage, Repository, Documentation, and Bug Tracker links so PyPI renders them.
- Acceptance: PyPI project page shows all four URL fields.

AC-013 | Update PyPI Classifiers and Python Support
- Priority: P2 | Scope: Packaging | Sources: C-B13, C-B14, G
- Description: Add `Topic :: Scientific/Engineering :: Artificial Intelligence` classifier and Python 3.13 to classifiers. Test against 3.13.
- Acceptance: PyPI classifiers include AI/ML tag and Python 3.13; CI passes on 3.13.

AC-014 | Audit Dependency Version Constraints
- Priority: P1 | Scope: Packaging | Sources: C-B15, C-B16, G, M
- Description: Review and fix risky constraints: `langchain<1.0.0` may cause conflicts; `litellm>=1.81.5` lacks upper bound. Pin major versions or use compatible release clauses.
- Acceptance: `pip install` resolves without conflicts on a fresh environment; no unbounded major dependencies remain.

AC-015 | Clarify Memory Dependency Status
- Priority: P1 | Scope: Packaging | Sources: C-B17, C-F54, G
- Description: `mem0ai` is under `[memory]` extra but the README implies persistent memory is a core feature. Either make it a core dependency or explicitly document `pip install amberclaw-ai[memory]`.
- Acceptance: README clearly states memory is optional and shows the exact install command.

AC-016 | Add Vector Database Dependencies to Extras
- Priority: P1 | Scope: Packaging | Sources: C-B18, K-7
- Description: Add `chroma`, `lancedb`, or `qdrant-client` to optional extras so users can enable RAG without manual dependency management.
- Acceptance: `pip install amberclaw-ai[vectordb]` installs a vector store backend.

AC-017 | Remove Type-Check and Lint Exclusions
- Priority: P2 | Scope: Quality | Sources: C-B19, C-B20
- Description: `pyright` excludes `amberclaw/channels`; `ruff` excludes `amberclaw/data` and `amberclaw/skills`. Remove exclusions and fix underlying issues.
- Acceptance: Zero directories are excluded from pyright or ruff; CI passes.

AC-018 | Enforce Test Coverage Threshold in CI
- Priority: P2 | Scope: Quality | Sources: C-B21, C-D31, G
- Description: Add `--cov-fail-under=70` (or chosen threshold) to pytest config and display a coverage badge in README.
- Acceptance: CI fails if coverage drops below threshold; badge reflects current percentage.

AC-019 | Publish Working PyPI Package with Entry Points
- Priority: P0 | Scope: Packaging | Sources: C-B11, G, M
- Description: Ensure `amberclaw-ai` (or canonical name) is actually published on PyPI with working CLI entry points (`amberclaw`, `onboard`).
- Acceptance: `pip install amberclaw-ai` followed by `amberclaw --help` works on a clean machine.

AC-020 | Create One-Command Bootstrap Script
- Priority: P2 | Scope: Packaging | Sources: G
- Description: Combine installation, `onboard`, and optional Docker setup into a single curl/bash or Python bootstrap command.
- Acceptance: New users can run one command to get a working local setup.

AC-021 | Build and Publish Multi-Arch Docker Images to GHCR
- Priority: P2 | Scope: Packaging | Sources: C-C26, G
- Description: Add GitHub Actions workflow to build and push `linux/amd64` and `linux/arm64` images to GitHub Container Registry on every release tag.
- Acceptance: `docker pull ghcr.io/krishujeniya/amberclaw:latest` succeeds on both x86_64 and ARM64.

AC-022 | Verify uv and pip Install Paths
- Priority: P1 | Scope: Packaging | Sources: G
- Description: Test and document both `uv tool install amberclaw-ai` and `pip install amberclaw-ai` paths.
- Acceptance: Both installation methods are documented and tested in CI.

---

3. DOCUMENTATION & DEVELOPER EXPERIENCE

AC-023 | Create Dedicated Documentation Site
- Priority: P1 | Scope: Documentation | Sources: C-F52, K-56, G, M
- Description: Set up MkDocs, Mintlify, or Sphinx with sidebar navigation, search, and versioning. A README-only project is insufficient for a framework.
- Acceptance: Public docs site is live with ≥5 top-level sections.

AC-024 | Add Auto-Generated API Reference
- Priority: P1 | Scope: Documentation | Sources: C-F53, K-56, G
- Description: Use `pdoc`, `mkdocstrings`, or Sphinx autodoc to generate API docs from docstrings.
- Acceptance: Every public module, class, and function appears in the API reference.

AC-025 | Expand README with Value Proposition and Comparison Table
- Priority: P1 | Scope: Documentation | Sources: C-F57, G, M
- Description: Add a "Why AmberClaw?" section highlighting the 4k LOC advantage versus LangChain, CrewAI, AutoGen, and Open WebUI. Include a feature comparison table.
- Acceptance: README contains a comparison table with ≥4 competitor frameworks.

AC-026 | Add Written Architecture Deep-Dive
- Priority: P1 | Scope: Documentation | Sources: C-F60, G, M
- Description: Explain the message flow in prose: user message → channel → bus → agent → tool → memory → response. Embed and annotate the existing architecture diagram.
- Acceptance: Docs contain a step-by-step message flow explanation with diagram.

AC-027 | Provide Ready-to-Copy Sample Config Files
- Priority: P1 | Scope: Documentation | Sources: C-F58, G, M
- Description: Create `config.telegram-claude.json`, `config.discord-local.json`, etc., in an `/examples/configs` directory.
- Acceptance: ≥3 common setup configs are available for immediate copy-paste.

AC-028 | Add Comprehensive Troubleshooting Guide
- Priority: P2 | Scope: Documentation | Sources: C-F56, G, M
- Description: Document common failures: WhatsApp Node.js dependency, Feishu/DingTalk firewall issues, Matrix homeserver setup, provider auth errors, and Docker volume mounting.
- Acceptance: Troubleshooting section covers ≥8 common failure modes with solutions.

AC-029 | Add Windows Setup Documentation
- Priority: P2 | Scope: Documentation | Sources: C-F59, G
- Description: Provide Windows installation steps and a Windows Service equivalent to the systemd setup.
- Acceptance: Windows users have a documented path to run AmberClaw as a background service.

AC-030 | Add Version Migration Guides
- Priority: P2 | Scope: Documentation | Sources: K-60, G
- Description: Create `MIGRATION.md` explaining how to upgrade between versions (e.g., config format changes, dependency updates).
- Acceptance: Migration guide exists for every breaking change.

AC-031 | Create /examples Directory with Ready-to-Run Demos
- Priority: P1 | Scope: Documentation | Sources: C-F58, G, M
- Description: Include ≥10 working examples: basic agent, custom skill, MCP filesystem server, multi-agent workflow, WhatsApp integration, RAG pipeline.
- Acceptance: Each example has a README and runs without modification after config.

AC-032 | Produce Video Tutorials or Screen Recordings
- Priority: P2 | Scope: Documentation | Sources: K-59, G
- Description: Create short videos for: installation, first skill creation, MCP server connection, and Docker deployment.
- Acceptance: ≥3 tutorial videos are linked from the main README or docs site.

AC-033 | Explicitly Document Memory Extra Installation
- Priority: P1 | Scope: Documentation | Sources: C-F54, G
- Description: State clearly in README that persistent cross-session memory requires `pip install amberclaw-ai[memory]`.
- Acceptance: README contains a callout box explaining the memory extra.

AC-034 | Document --all-extras Installation for Full Features
- Priority: P2 | Scope: Documentation | Sources: C-F55, G
- Description: Show the command `pip install amberclaw-ai[all]` (or equivalent) and explain what each extra enables.
- Acceptance: Installation section lists all extras and their purposes.

AC-035 | Publish Skill Development Guide and SKILL.md Spec
- Priority: P1 | Scope: Documentation | Sources: G, M
- Description: Explain the skill directory structure, manifest format, and how to publish to ClawHub.
- Acceptance: Dedicated "Building Skills" docs page exists with a Hello-World skill tutorial.

AC-036 | Add "vs Alternatives" Comparison Document
- Priority: P2 | Scope: Documentation | Sources: C-F57, G
- Description: Compare AmberClaw against OpenClaw, AutoGen, CrewAI, LangGraph, and Open WebUI on lines of code, startup time, memory usage, and feature set.
- Acceptance: Comparison doc/table is present and maintained.

AC-037 | Maintain Detailed CHANGELOG with Conventional Format
- Priority: P2 | Scope: Documentation | Sources: C-F61, G
- Description: Replace single-entry CHANGELOG with a conventional format (Keep a Changelog) tracking every meaningful change.
- Acceptance: CHANGELOG has entries for every commit since last release with Added/Changed/Fixed/Security headers.

---

4. TESTING, CODE QUALITY & MAINTAINABILITY

AC-038 | Enforce Comprehensive Type Hints Across All Modules
- Priority: P1 | Scope: Quality | Sources: C-B19, G, M
- Description: Add type hints to all functions and classes; run `mypy` and `pyright` in CI with zero tolerance.
- Acceptance: `mypy amberclaw/` passes with no errors; no directories are excluded.

AC-039 | Set Up Pre-Commit Hooks for Linting and Formatting
- Priority: P2 | Scope: Quality | Sources: G, M
- Description: Configure `.pre-commit-config.yaml` with ruff, black, isort, and pyright hooks.
- Acceptance: Contributors cannot commit code that fails lint or type checks.

AC-040 | Expand Unit Tests for Core Modules
- Priority: P1 | Scope: Quality | Sources: C, G, M
- Description: Write tests for config schema validation, provider registry, agent loop logic, skill loader, and security guards.
- Acceptance: Core modules have ≥80% unit test coverage.

AC-041 | Add Integration Tests with Mocked Chat Platforms
- Priority: P1 | Scope: Quality | Sources: K-53, G
- Description: Create mocked Telegram, Discord, and Slack clients to test end-to-end message flow without live APIs.
- Acceptance: CI runs integration tests against mocked channels.

AC-042 | Add Prompt Regression Tests
- Priority: P2 | Scope: Quality | Sources: K-54, G
- Description: Snapshot-test critical prompts to detect accidental behavior changes when prompts are modified.
- Acceptance: Prompt changes trigger reviewable diffs in CI.

AC-043 | Add Load Tests for Concurrent Gateway Connections
- Priority: P2 | Scope: Quality | Sources: K-55, G
- Description: Use `locust` or `k6` to simulate concurrent users hitting the gateway on port 18790.
- Acceptance: Load test runs in CI nightly; reports latency p50/p95/p99.

AC-044 | Add Property-Based Testing for Config Validation
- Priority: P3 | Scope: Quality | Sources: K-55
- Description: Use `hypothesis` to generate random config objects and ensure Pydantic validation never crashes.
- Acceptance: Property-based tests run and pass in CI.

AC-045 | Add Dependency Vulnerability Scanning
- Priority: P1 | Scope: Security/Quality | Sources: C-D29, G
- Description: Integrate Dependabot or `pip-audit` into CI to catch vulnerable dependencies on PRs.
- Acceptance: CI fails if a PR introduces a dependency with known CVE.

AC-046 | Add CodeQL Static Analysis Workflow
- Priority: P2 | Scope: Security/Quality | Sources: C-D32, G
- Description: Enable GitHub CodeQL for Python to detect common security anti-patterns.
- Acceptance: CodeQL analysis runs on every PR and push to main.

AC-047 | Add Secret Scanning Workflow
- Priority: P1 | Scope: Security/Quality | Sources: C-D30, K-33, G
- Description: Use TruffleHog or git-secrets in CI to prevent API keys from being committed.
- Acceptance: CI fails if a commit contains a high-entropy string matching API key patterns.

AC-048 | Provide Fake AI Response Fixtures for Offline Testing
- Priority: P2 | Scope: Quality | Sources: G, M
- Description: Create a test fixture that mocks LiteLLM responses so contributors can run tests without API keys or spending tokens.
- Acceptance: Full test suite passes with `MOCK_LLM=true` environment variable.

---

5. CORE AGENT ARCHITECTURE & INTELLIGENCE

AC-049 | Implement Plan-Execute-Reflect Agent Loop
- Priority: P1 | Scope: Feature | Sources: C-E45, K-11, G
- Description: Replace the simple Message→LLM→Tools→Response loop with a configurable Plan-Execute-Reflect cycle where the agent plans steps, executes, and reflects before responding.
- Acceptance: Agent can be configured to use ReAct, Plan-and-Execute, or simple mode.

AC-050 | Add Reflection Module for Self-Evaluation
- Priority: P1 | Scope: Feature | Sources: K-12, G
- Description: After generating a response or tool call, the agent evaluates its own output for correctness, completeness, and safety, then self-corrects if needed.
- Acceptance: Reflection step is observable in logs and improves task success rate.

AC-051 | Add Multi-Step Planning Capabilities
- Priority: P1 | Scope: Feature | Sources: C-E45, K-14, G
- Description: Enable the agent to break complex user requests into sub-tasks, execute them sequentially or in parallel, and aggregate results.
- Acceptance: Agent successfully handles a 3+ step task (e.g., "search web, summarize, send email") without human intervention.

AC-052 | Add Hierarchical Agent Orchestration
- Priority: P1 | Scope: Feature | Sources: K-15, G
- Description: Support supervisor agents that delegate to worker/sub-agents, and swarm patterns for collaborative task solving.
- Acceptance: A parent agent can spawn and coordinate ≥2 child agents to complete a composite task.

AC-053 | Add Self-Improvement Feedback Loops
- Priority: P2 | Scope: Feature | Sources: C-E45, K-16, G
- Description: Capture user corrections (thumbs up/down, explicit edits) and feed them back into memory or prompt tuning to improve future responses.
- Acceptance: User corrections measurably influence similar future queries.

AC-054 | Integrate LangGraph for Stateful Multi-Actor Workflows
- Priority: P1 | Scope: Feature | Sources: K-13, G
- Description: Deepen the existing LangGraph dependency usage to build persistent, interruptible, and branchable agent workflows.
- Acceptance: Complex workflows can be paused, resumed, and visualized as graphs.

AC-055 | Add Structured Output Enforcement with Retry Logic
- Priority: P1 | Scope: Feature | Sources: C-E44, K-48, G
- Description: When a model returns malformed JSON for a tool call, automatically retry with a correction prompt instead of crashing. Leverage existing `json-repair` dependency.
- Acceptance: Zero crashes due to malformed tool-call JSON in 1000 test invocations.

AC-056 | Add Reasoning Model Integration
- Priority: P2 | Scope: Feature | Sources: K-18
- Description: Support reasoning-specific parameters (`reasoning_effort`, `thinking`) for o3, Claude 4, and similar models.
- Acceptance: Reasoning models can be configured and their reasoning tokens are exposed/logs.

AC-057 | Add Computer Use / GUI Automation Skills
- Priority: P2 | Scope: Feature | Sources: K-19
- Description: Build skills for desktop automation (mouse/keyboard) and browser control (playwright/selenium) with safety guards.
- Acceptance: Agent can perform a supervised browser search or file operation via a skill.

AC-058 | Implement Agent Evaluation Framework
- Priority: P1 | Scope: Feature | Sources: C-E46, K-37, G
- Description: Create a harness to define expected tool calls and responses, then measure tool call accuracy, hallucination rate, and latency.
- Acceptance: CI runs agent evals and reports pass/fail metrics.

AC-059 | Add Token and Context Budget System
- Priority: P2 | Scope: Feature | Sources: C-E51, G
- Description: Warn or truncate when approaching a model's context window limit in long sessions. Track token usage per turn.
- Acceptance: Users receive a warning at 80% context capacity; automatic summarization triggers at 95%.

---

6. MEMORY, KNOWLEDGE & RAG SYSTEMS

AC-060 | Upgrade to Mem0 v1.0+ with Graph Memory
- Priority: P1 | Scope: Feature | Sources: C-E39, K-1
- Description: Upgrade from basic mem0ai to v1.0+ which supports knowledge graph features for multi-hop reasoning.
- Acceptance: Memory system supports graph queries and entity relationships.

AC-061 | Integrate Temporal Knowledge Graphs
- Priority: P1 | Scope: Feature | Sources: K-4, K-61
- Description: Add Zep/Graphiti or Cognee integration to track facts with timestamps (e.g., "Alice was lead until February, then Bob took over").
- Acceptance: Queries about past states return correct temporal answers.

AC-062 | Add Vector Database Backends
- Priority: P1 | Scope: Feature | Sources: C-E38, K-7, G
- Description: Support Chroma, LanceDB, or Qdrant as configurable vector stores for embeddings and retrieval.
- Acceptance: User can switch vector backend via config; default works out-of-the-box.

AC-063 | Implement Hybrid Retrieval (Vector + Keyword + Rerank)
- Priority: P1 | Scope: Feature | Sources: K-8
- Description: Combine dense vector search, BM25 keyword search, and a cross-encoder reranker for optimal document retrieval.
- Acceptance: Retrieval accuracy on test set exceeds pure vector search by ≥10%.

AC-064 | Add Automatic Knowledge Graph Construction
- Priority: P2 | Scope: Feature | Sources: K-9
- Description: Extract entities and relationships from conversations automatically and store them in a graph structure.
- Acceptance: New entities appear in the knowledge graph after each conversation turn.

AC-065 | Add Memory Extraction Pipelines
- Priority: P1 | Scope: Feature | Sources: K-2
- Description: Convert raw conversation history into atomic facts with entity resolution and deduplication.
- Acceptance: Conversations are distilled into a set of unique, queryable facts.

AC-066 | Add Temporal Memory Tracking
- Priority: P2 | Scope: Feature | Sources: K-4
- Description: Tag memories with validity periods so the agent knows when a fact was true.
- Acceptance: Agent correctly answers "Who was the lead in January?" versus "Who is the lead now?"

AC-067 | Add Institutional Knowledge Extraction
- Priority: P2 | Scope: Feature | Sources: K-5
- Description: Extract lessons learned, best practices, and domain expertise from repeated interactions to build organizational knowledge.
- Acceptance: Agent accumulates domain-specific guidance over time.

AC-068 | Add Multi-Scope Memory Scoping
- Priority: P2 | Scope: Feature | Sources: K-6
- Description: Support `user_id`, `agent_id`, `session_id`, and `org_id` scoping so memories are retrieved at the correct granularity.
- Acceptance: Multi-user deployments isolate memories per user by default.

AC-069 | Make Persistent Cross-Session Memory Default
- Priority: P1 | Scope: Feature | Sources: C-E39, G
- Description: Current default install has no persistent memory. Either make it default or prominently document how to enable it.
- Acceptance: Fresh install retains conversation context across restarts without extra configuration.

AC-070 | Build RAG / Document Knowledge Base Pipeline
- Priority: P1 | Scope: Feature | Sources: C-E37, K-10, G
- Description: Allow users to point AmberClaw at a folder of documents and ask questions against them. Include ingestion, chunking, embedding, and retrieval.
- Acceptance: User can run `amberclaw ingest ./docs` and then query the knowledge base.

AC-071 | Add Multi-Source Document Ingestion
- Priority: P2 | Scope: Feature | Sources: K-10, G
- Description: Support PDF, markdown, plaintext, DOCX, and HTML ingestion using `unstructured` (already in docs extras).
- Acceptance: All listed formats can be ingested without errors.

AC-072 | Add RAGAS-Based Retrieval Quality Evaluation
- Priority: P2 | Scope: Feature | Sources: C-E37, K-37
- Description: Use RAGAS metrics (faithfulness, answer relevancy, context precision) to evaluate and improve the RAG pipeline.
- Acceptance: RAG pipeline has an eval script that reports RAGAS scores.

---

7. MULTI-MODAL CAPABILITIES

AC-073 | Add Vision Tool Using Multimodal APIs
- Priority: P1 | Scope: Feature | Sources: C-E34, K-20, G
- Description: Wire image inputs from chat platforms into vision-capable models (GPT-4o, Claude 3, Gemini).
- Acceptance: Sending an image to the bot yields a descriptive response.

AC-074 | Support Image Inputs Across All Chat Platforms
- Priority: P1 | Scope: Feature | Sources: K-24, G
- Description: Ensure Telegram, Discord, Slack, and other channels can upload and forward images to the agent.
- Acceptance: Image upload works on ≥3 platforms.

AC-075 | Integrate Whisper for Speech-to-Text
- Priority: P1 | Scope: Feature | Sources: C-E35, K-21, G
- Description: Add voice message handling via OpenAI Whisper or Groq Whisper for speech input.
- Acceptance: User sends a voice message; agent receives transcribed text.

AC-076 | Add Text-to-Speech Output
- Priority: P2 | Scope: Feature | Sources: C-E35, K-22, G
- Description: Support TTS via ElevenLabs, Kokoro, or similar for voice responses.
- Acceptance: Agent can reply with an audio file on supported platforms.

AC-077 | Add Real-Time Video Processing
- Priority: P3 | Scope: Feature | Sources: K-25
- Description: Enable processing of video inputs (frame extraction + description) for multimodal models.
- Acceptance: Short video clips can be summarized by the agent.

AC-078 | Leverage Unstructured for Rich Document Ingestion
- Priority: P2 | Scope: Feature | Sources: K-23
- Description: Use the already-included `unstructured` library to parse tables, headers, and images from documents.
- Acceptance: Complex PDFs with tables are ingested with structure preserved.

AC-079 | Add Real-Time Sensor Inputs for Desktop Use
- Priority: P3 | Scope: Feature | Sources: G
- Description: Support webcam and microphone streams for local/edge deployments.
- Acceptance: Desktop agent can access webcam feed on request.

---

8. LLM PROVIDERS, MODELS & ROUTING

AC-080 | Fix Non-Existent Default Model Names
- Priority: P0 | Scope: Config | Sources: K-38
- Description: `anthropic/claude-opus-4-5` does not exist. Update to real model identifiers.
- Acceptance: Default config points to a model that returns a valid response.

AC-081 | Update Default Models to Current SOTA
- Priority: P1 | Scope: Config | Sources: K-39
- Description: Set defaults to Claude 4 Opus, GPT-4.1, or Gemini 2.5 Pro depending on provider.
- Acceptance: Out-of-the-box experience uses a top-tier 2026 model.

AC-082 | Add Missing LLM Providers
- Priority: P1 | Scope: Feature | Sources: K-40–44
- Description: Add native support for xAI/Grok, Cohere Command R+, Mistral Large, Amazon Bedrock, and NVIDIA NIM.
- Acceptance: Each new provider can be configured and successfully routes requests via LiteLLM.

AC-083 | Add Model Capability Detection
- Priority: P2 | Scope: Feature | Sources: K-46
- Description: Automatically detect whether a model supports vision, function calling, JSON mode, and context window size.
- Acceptance: Agent refuses or warns when a capability is requested from an incompatible model.

AC-084 | Implement Automatic Provider Fallback Routing
- Priority: P1 | Scope: Feature | Sources: G
- Description: If the primary provider fails (rate limit, downtime), automatically retry with a secondary provider.
- Acceptance: Primary provider failure results in seamless fallback within 5 seconds.

AC-085 | Add Per-Provider and Per-Session Cost Tracking
- Priority: P1 | Scope: Feature | Sources: C-E41, K-35, G
- Description: Log token usage and estimated cost for every LLM call, aggregated by provider and session.
- Acceptance: `amberclaw cost` or dashboard shows accurate spend breakdown.

AC-086 | Add Token Usage Monitoring Dashboard
- Priority: P2 | Scope: Feature | Sources: K-36, G
- Description: Expose Prometheus metrics or a simple CLI command for token consumption trends.
- Acceptance: Metrics endpoint or command returns token counts per provider over time.

AC-087 | Extend Prompt Caching to All Providers
- Priority: P2 | Scope: Feature | Sources: K-47
- Description: Currently only Anthropic prompt caching is mentioned. Implement caching for OpenAI, Gemini, and others where supported.
- Acceptance: Repeated similar prompts hit cache and reduce token cost.

AC-088 | Enforce JSON Mode / Structured Outputs for Tool Calls
- Priority: P1 | Scope: Feature | Sources: K-48
- Description: Use native JSON mode or structured output constraints on all providers that support it to reduce malformed responses.
- Acceptance: Tool call JSON parse failure rate drops below 1%.

AC-089 | Add Streaming Response Support
- Priority: P1 | Scope: Feature | Sources: C-E33, G
- Description: Stream LLM responses to chat platforms with typing indicators instead of waiting for full generation.
- Acceptance: Telegram/Discord show "typing…" and text appears incrementally.

AC-090 | Add Latency Monitoring per Provider
- Priority: P2 | Scope: Feature | Sources: K-36, G
- Description: Track and log time-to-first-token and total generation time per provider.
- Acceptance: Latency metrics are visible in logs and tracing dashboards.

AC-091 | Improve Local/Offline-First Support with Ollama Quickstart
- Priority: P1 | Scope: Documentation/Feature | Sources: C-E50, G, M
- Description: Create a dedicated "Run Fully Local" guide using Ollama, and ensure `langchain-ollama` integration is documented.
- Acceptance: New user can run AmberClaw with zero API keys in under 10 minutes.

AC-092 | Add Local Model Optimizations
- Priority: P2 | Scope: Feature | Sources: K-61–62, G
- Description: Support quantization (GGUF), speculative decoding, and LoRA adapter loading for local models.
- Acceptance: Local model inference is measurably faster with optimizations enabled.

---

9. MCP, PROTOCOLS & TOOL ECOSYSTEM

AC-093 | Upgrade MCP to Latest 2026 Specification
- Priority: P1 | Scope: Feature | Sources: K-26
- Description: Ensure compatibility with the latest Model Context Protocol spec, including newer transports and enterprise features.
- Acceptance: MCP servers using the 2026 spec connect and function correctly.

AC-094 | Add A2A (Agent-to-Agent) Protocol Support
- Priority: P1 | Scope: Feature | Sources: K-27, K-17
- Description: Implement the Agent-to-Agent protocol for inter-agent communication and collaboration.
- Acceptance: Two AmberClaw instances can discover and message each other via A2A.

AC-095 | Implement MCP Server Discovery and Dynamic Registration
- Priority: P2 | Scope: Feature | Sources: K-28
- Description: Auto-discover available MCP servers on the network and register their tools dynamically.
- Acceptance: New MCP server appears in tool list without config restart.

AC-096 | Build Built-In Web Search Tool
- Priority: P1 | Scope: Feature | Sources: C-E36, K-96, G
- Description: Bundle a web search tool using Tavily, Brave Search API, or SerpAPI that works out-of-the-box without MCP configuration.
- Acceptance: `search_web("query")` tool works immediately after setting an API key.

AC-097 | Deepen ClawHub / OpenClaw Compatibility
- Priority: P1 | Scope: Feature | Sources: G
- Description: Full support for discovering, installing, and running SKILL.md-based skills from the ClawHub registry.
- Acceptance: `amberclaw skill install clawhub:skill-name` works end-to-end.

AC-098 | Add CLI Skill Install Command
- Priority: P1 | Scope: Feature | Sources: C-E49, G
- Description: Implement `amberclaw skill install <url/slug>` with dependency resolution and verification.
- Acceptance: CLI can install a skill from GitHub URL or ClawHub slug.

AC-099 | Support Standard Tool Formats Beyond MCP
- Priority: P2 | Scope: Feature | Sources: G
- Description: Support OpenAI function calling, Anthropic tool use, and LangChain tool formats natively.
- Acceptance: Tools defined in any of these formats execute without wrapper translation.

AC-100 | Create Curated, Security-Verified Skill Collection
- Priority: P1 | Scope: Feature | Sources: G
- Description: Maintain an official list of vetted skills with security badges and version pinning.
- Acceptance: Curated registry exists with ≥10 verified skills.

AC-101 | Add Skill Security Scanning Before Loading
- Priority: P1 | Scope: Security | Sources: G
- Description: Scan skills for prompt injection, credential exfiltration, and malicious shell commands before execution.
- Acceptance: Loading a malicious skill is blocked and logged.

AC-102 | Add Skill Versioning and Marketplace Infrastructure
- Priority: P2 | Scope: Feature | Sources: C-E49, G
- Description: Support skill versioning, dependency management, and a community marketplace with ratings.
- Acceptance: Skills can specify version ranges and dependencies; marketplace UI exists.

---

10. SECURITY, SAFETY & COMPLIANCE

AC-103 | Fix Dockerfile to Run as Non-Root User
- Priority: P0 | Scope: Security | Sources: C-C22, G
- Description: Add a `USER` directive in the Dockerfile final stage; do not run as root.
- Acceptance: Container runs as UID ≥1000; `whoami` inside container returns non-root.

AC-104 | Encrypt API Keys at Rest
- Priority: P0 | Scope: Security | Sources: C-G62, G
- Description: Use the existing `keyring` dependency to store API keys in the OS credential store instead of plaintext `~/.AmberClaw/config.json`.
- Acceptance: Config file contains no plaintext API keys; keys are retrieved from OS keyring.

AC-105 | Add PII Detection and Redaction
- Priority: P1 | Scope: Security | Sources: K-29, G
- Description: Integrate Presidio or similar to detect and redact personally identifiable information in logs and memory.
- Acceptance: PII (emails, phone numbers, SSNs) is redacted in all persistent storage.

AC-106 | Implement Sandboxed Code Execution
- Priority: P1 | Scope: Security | Sources: K-30, G
- Description: Run shell/code tools inside Firejail, gVisor, or a disposable Docker container instead of the host.
- Acceptance: A malicious `rm -rf /` command inside a tool is contained and cannot harm the host.

AC-107 | Add Structured, Immutable Audit Logs
- Priority: P1 | Scope: Security | Sources: K-31, G
- Description: Log every tool execution, API key access, and config change to an append-only, tamper-evident log.
- Acceptance: Audit log cannot be modified by the application user; entries are cryptographically chained or WORM-stored.

AC-108 | Support Role-Based Access Control (RBAC)
- Priority: P1 | Scope: Security | Sources: K-32, G
- Description: Replace binary allow/block with roles (admin, user, guest) that have different permission sets.
- Acceptance: Config supports role definitions; agent enforces role-based tool access.

AC-109 | Add Secret Scanning Prevention in Logs
- Priority: P1 | Scope: Security | Sources: K-33, G
- Description: Ensure API keys and tokens are never printed in logs, tracebacks, or error messages.
- Acceptance: Log inspection reveals zero leaked secrets under normal and error conditions.

AC-110 | Strengthen Tool Sandboxing and Default restrictToWorkspace
- Priority: P0 | Scope: Security | Sources: C-E43, C-G64, G
- Description: Set `restrictToWorkspace` default to `true`. Add warnings in docs for `allowFrom: ["*"]`. Strengthen MCP sandboxing with syscall filtering where possible.
- Acceptance: Fresh install is sandboxed; dangerous configs require explicit opt-in with warnings.

AC-111 | Add Rate Limiting on Outgoing LLM Calls
- Priority: P1 | Scope: Security | Sources: C-E42, G
- Description: Throttle cron/heartbeat and user-triggered requests to prevent provider rate limits and cost spikes.
- Acceptance: Burst of 100 requests is smoothed to provider-safe rates; user can configure RPM limits.

AC-112 | Add Input Sanitization and Output Filtering
- Priority: P1 | Scope: Security | Sources: G
- Description: Sanitize all channel inputs and filter outputs for dangerous content (prompt injection, XSS, control characters).
- Acceptance: Known prompt injection payloads are neutralized.

AC-113 | Disclose WhatsApp Node.js Subprocess Risks
- Priority: P1 | Scope: Security | Sources: C-G63, G
- Description: Document that the WhatsApp integration spawns an unaudited Node.js process and advise on isolation.
- Acceptance: SECURITY.md and README contain a clear disclosure about WhatsApp bridge risks.

AC-114 | Add SLSA Provenance and SBOM Generation
- Priority: P2 | Scope: Security | Sources: C-G65, C-G66, G
- Description: Generate signed build attestations and a Software Bill of Materials for every release.
- Acceptance: Release artifacts include `.provenance` and `.sbom.json` files.

AC-115 | Support External Secret Management
- Priority: P2 | Scope: Security | Sources: G
- Description: Allow integration with 1Password, HashiCorp Vault, or environment variables for secrets instead of config files.
- Acceptance: Agent starts successfully with all secrets provided via env vars or vault references.

---

11. OBSERVABILITY, EVALUATION & TRACING

AC-116 | Integrate OpenTelemetry for Distributed Tracing
- Priority: P1 | Scope: Infra | Sources: C-E40, K-34, G
- Description: Instrument the agent loop, tool calls, and channel handlers with OpenTelemetry spans.
- Acceptance: Traces are exportable to Jaeger, Zipkin, or OTLP collectors.

AC-117 | Add LLM Tracing Integration (Langfuse / Phoenix / Traceloop)
- Priority: P1 | Scope: Infra | Sources: C-E40, K-34, G
- Description: Integrate with Langfuse, Arize Phoenix, or Traceloop for visual debugging of agent runs.
- Acceptance: Every agent run is visible in the tracing UI with prompts, completions, and tool calls.

AC-118 | Create Evaluation Suite Using LLM-as-a-Judge
- Priority: P1 | Scope: Quality | Sources: K-37, G
- Description: Build an eval harness that scores agent outputs on helpfulness, accuracy, and safety using a reference model.
- Acceptance: CI runs eval suite and reports scores on PRs.

AC-119 | Add Cost Tracking Dashboard
- Priority: P1 | Scope: Feature | Sources: C-E41, K-35, G
- Description: Provide a CLI command or web view showing spend per provider, per session, and per day.
- Acceptance: `amberclaw cost --dashboard` opens a local web page with charts.

AC-120 | Add Latency Monitoring for Tool Calls
- Priority: P2 | Scope: Infra | Sources: K-36, G
- Description: Track and alert on slow tool executions (e.g., MCP server timeout, web search delay).
- Acceptance: Slow tools trigger warnings in logs; metrics are exposed.

AC-121 | Add Prometheus Metrics Endpoint
- Priority: P2 | Scope: Infra | Sources: G
- Description: Expose `/metrics` on the gateway for Prometheus scraping (request count, latency, error rate, token usage).
- Acceptance: Prometheus can scrape the gateway; Grafana dashboard template is provided.

AC-122 | Add Performance Benchmarking Against Competitors
- Priority: P2 | Scope: Quality | Sources: G
- Description: Run standardized benchmarks (latency, token efficiency, success rate) versus AutoGen, CrewAI, and LangGraph.
- Acceptance: Benchmark results are published in docs and updated monthly.

AC-123 | Implement RAGAS-Based Retrieval Evaluation
- Priority: P2 | Scope: Quality | Sources: C-E37, K-37
- Description: Evaluate RAG pipeline using faithfulness, answer relevancy, and context precision metrics.
- Acceptance: RAG eval script runs and reports scores ≥0.7 on test dataset.

---

12. DEPLOYMENT, SCALING & INFRASTRUCTURE

AC-124 | Separate Slim / Gateway-Only Docker Image
- Priority: P1 | Scope: Infra | Sources: C-C24, G
- Description: Create `Dockerfile.gateway` that installs only core + channels extras, avoiding heavy ML dependencies.
- Acceptance: Gateway-only image is <300MB; full image is available separately.

AC-125 | Add HTTP Healthcheck Endpoint
- Priority: P1 | Scope: Infra | Sources: C-C25, G
- Description: Replace `amberclaw status` CLI healthcheck with `GET /health` on the gateway (port 18790).
- Acceptance: Docker healthcheck and load balancers can poll `/health` successfully.

AC-126 | Add GitHub Actions for GHCR Publishing
- Priority: P2 | Scope: Infra | Sources: C-C26, G
- Description: Auto-build and push Docker images to GitHub Container Registry on release tags.
- Acceptance: Tagged release automatically appears on GHCR within 10 minutes.

AC-127 | Add Multi-Architecture Docker Builds
- Priority: P2 | Scope: Infra | Sources: C-C27, G
- Description: Target `linux/amd64` and `linux/arm64` for Raspberry Pi and Apple Silicon deployment.
- Acceptance: `docker run` works natively on M-series Macs and Raspberry Pi 4/5.

AC-128 | Add Kubernetes Helm Charts
- Priority: P2 | Scope: Infra | Sources: K-51, G
- Description: Provide a Helm chart with configurable replicas, resources, ingress, and persistence.
- Acceptance: `helm install amberclaw ./chart` deploys to a K8s cluster.

AC-129 | Support PostgreSQL as Alternative to SQLite
- Priority: P1 | Scope: Infra | Sources: K-49, G
- Description: Allow `database_url` to point to PostgreSQL for production durability and concurrency.
- Acceptance: All SQLite functionality works identically on Postgres; migration script provided.

AC-130 | Add Redis for Distributed State and Pub/Sub
- Priority: P1 | Scope: Infra | Sources: K-50, G
- Description: Use Redis for session state, caching, and inter-instance communication in multi-instance deployments.
- Acceptance: Two gateway instances share state via Redis; pub/sub works for real-time updates.

AC-131 | Create Serverless Deployment Examples
- Priority: P2 | Scope: Infra | Sources: K-52, G
- Description: Provide templates for AWS Lambda, Google Cloud Run, and Vercel deployment.
- Acceptance: Each serverless example has a README and deploys successfully.

AC-132 | Support Environment Variables for Secrets
- Priority: P1 | Scope: Infra | Sources: G
- Description: Allow all config values (especially secrets) to be overridden via environment variables.
- Acceptance: `AMBERCLAW_OPENAI_KEY=sk-... amberclaw gateway` works without config file.

AC-133 | Add Horizontal Scaling Support for Gateway
- Priority: P2 | Scope: Infra | Sources: G
- Description: Ensure the gateway is stateless or uses shared storage so multiple instances can run behind a load balancer.
- Acceptance: Load test with 3 gateway instances shows linear throughput scaling.

AC-134 | Enhance Docker Compose with Profiles and Healthchecks
- Priority: P2 | Scope: Infra | Sources: G
- Description: Add service profiles (agent-only, gateway-only, full), healthchecks, and named volumes to `compose.yaml`.
- Acceptance: `docker compose --profile gateway up` starts only gateway services.

AC-135 | Improve Systemd Service Template
- Priority: P2 | Scope: Infra | Sources: G
- Description: Add journald logging, restart policies, and environment file support to the systemd unit example.
- Acceptance: Systemd service file is production-ready with auto-restart on failure.

---

13. CHANNELS, INTEGRATIONS & WEB UI

AC-136 | Add Self-Hosted Web UI
- Priority: P1 | Scope: Feature | Sources: C-E47, K-58, G, M
- Description: Build a minimal browser-based chat interface using Gradio, Streamlit, Chainlit, or a React app served from the gateway.
- Acceptance: Non-technical users can chat with the agent via a local web URL.

AC-137 | Add More Chat Platforms
- Priority: P2 | Scope: Feature | Sources: G
- Description: Add Signal, SMS gateways, and Telegram inline query support.
- Acceptance: Agent responds on Signal and SMS via configured adapters.

AC-138 | Improve WhatsApp Bridge Reliability
- Priority: P2 | Scope: Feature | Sources: G
- Description: Dockerize the Node.js WhatsApp bridge and add auto-restart and health monitoring.
- Acceptance: WhatsApp integration runs as a managed container with logs and healthchecks.

AC-139 | Add Calendar and Productivity Integrations
- Priority: P2 | Scope: Feature | Sources: C-E48, G
- Description: Integrate Google Calendar, Notion, Todoist, and GitHub for task and schedule management.
- Acceptance: Agent can read/create calendar events and todo items via skills.

AC-140 | Add Google Workspace and Email Automation
- Priority: P2 | Scope: Feature | Sources: G
- Description: Support Gmail, Google Docs, and Google Sheets operations through OAuth-enabled skills.
- Acceptance: Agent can summarize emails and append to sheets with user consent.

AC-141 | Add Smart Home Integration Hooks
- Priority: P3 | Scope: Feature | Sources: G
- Description: Provide Home Assistant MQTT/API hooks for voice/text control of IoT devices.
- Acceptance: Agent can turn on lights or read sensors via Home Assistant.

AC-142 | Improve Unified Messaging Bus
- Priority: P2 | Scope: Feature | Sources: G
- Description: Enhance the internal message bus to better handle multi-channel orchestration and message routing.
- Acceptance: Messages from different channels are routed correctly with channel metadata preserved.

AC-143 | Support Voice Channels Beyond Text
- Priority: P3 | Scope: Feature | Sources: G
- Description: Enable Discord voice channel and phone/SMS gateway support for voice conversations.
- Acceptance: User can talk to the agent in a Discord voice channel.

---

14. AUTOMATION, CRON & WORKFLOWS

AC-144 | Expand Cron/Heartbeat with Visual Workflow Builder
- Priority: P2 | Scope: Feature | Sources: G
- Description: Add a YAML or JSON workflow definition format with a simple visual editor for cron tasks.
- Acceptance: Users can define multi-step scheduled workflows without writing Python.

AC-145 | Add Proactive Agent Behaviors
- Priority: P2 | Scope: Feature | Sources: G
- Description: Allow the agent to initiate messages based on schedules, triggers, or monitored conditions.
- Acceptance: Agent sends a daily summary at 9 AM without user prompting.

AC-146 | Add Third-Party Automation Integrations
- Priority: P2 | Scope: Feature | Sources: G
- Description: Support Zapier, Make.com, or n8n webhooks for external trigger integration.
- Acceptance: External services can trigger AmberClaw workflows via HTTP webhooks.

AC-147 | Implement Multi-Step Workflow Engine
- Priority: P2 | Scope: Feature | Sources: G
- Description: Build a DAG-based workflow engine where nodes are skills/LLM calls and edges are conditions.
- Acceptance: Complex workflows with branching and loops can be defined and executed.

---

15. PERFORMANCE, EDGE & USABILITY

AC-148 | Optimize for Low-Resource and Edge Devices
- Priority: P2 | Scope: Performance | Sources: C-C27, G
- Description: Reduce memory footprint and CPU usage for Raspberry Pi and ARM edge deployment.
- Acceptance: Agent runs smoothly on Raspberry Pi 4 with 4GB RAM.

AC-149 | Add Streaming with Typing Indicators
- Priority: P1 | Scope: Feature | Sources: C-E33, G
- Description: Show typing indicators on Telegram/Discord while the model streams tokens.
- Acceptance: Users see real-time text appearance instead of a long wait.

AC-150 | Improve CLI with Interactive Features
- Priority: P2 | Scope: UX | Sources: G
- Description: Add progress indicators, `rich` formatting, and an interactive config editor (`amberclaw config --edit`).
- Acceptance: CLI provides visual feedback during long operations.

AC-151 | Benchmark Against Competitor Frameworks
- Priority: P2 | Scope: Quality | Sources: G
- Description: Measure and publish latency, memory usage, and lines-of-code comparisons versus CrewAI, AutoGen, and LangGraph.
- Acceptance: Benchmark page exists and is updated quarterly.

AC-152 | Add Simple Desktop App Wrapper
- Priority: P3 | Scope: UX | Sources: G
- Description: Provide an Electron or Tauri wrapper for users who prefer a native app over CLI/web.
- Acceptance: `.exe` / `.dmg` / `.AppImage` builds are available for major platforms.

AC-153 | Optimize Gateway for Concurrent Long-Running Sessions
- Priority: P2 | Scope: Performance | Sources: G
- Description: Ensure WebSocket or HTTP connections handle hundreds of concurrent sessions without memory leaks.
- Acceptance: Load test with 500 concurrent sessions shows stable memory usage.

---

16. COMMUNITY, ECOSYSTEM & ADOPTION

AC-154 | Create Dedicated Project Website with Live Demo
- Priority: P1 | Scope: Community | Sources: G
- Description: Build a landing page (e.g., amberclaw.dev) with feature highlights, documentation links, and a hosted demo bot.
- Acceptance: Website is live and linked from GitHub About section.

AC-155 | Publish Tutorials, Blog Posts, and Video Content
- Priority: P2 | Scope: Community | Sources: G, M
- Description: Create content for common use cases: personal productivity assistant, coding companion, research agent.
- Acceptance: ≥5 tutorials are published on Medium, Dev.to, or YouTube.

AC-156 | Engage OpenClaw / ClawHub Community
- Priority: P2 | Scope: Community | Sources: G
- Description: Contribute skills, request interoperability features, and build bridges with the OpenClaw ecosystem.
- Acceptance: AmberClaw skills are listed and installable from ClawHub.

AC-157 | Target Privacy-Focused Users with Local-First Guides
- Priority: P1 | Scope: Community | Sources: G
- Description: Market the fully local deployment path (Ollama + no cloud APIs) as a key differentiator.
- Acceptance: "100% Offline Mode" is a documented and tested deployment option.

AC-158 | Label Good First Issues and Offer Skill Bounties
- Priority: P3 | Scope: Community | Sources: G, M
- Description: Use GitHub labels to guide new contributors; offer small bounties for high-quality skills.
- Acceptance: ≥10 issues are labeled `good first issue`; bounty program is documented.

AC-159 | Monitor AI Agent Trends and Adapt Quickly
- Priority: P3 | Scope: Community | Sources: G
- Description: Track emerging protocols and standards; release compatibility updates within 30 days of major spec changes.
- Acceptance: Project maintains a public roadmap reflecting industry trends.

AC-160 | Highlight Ultra-Lightweight Positioning in Marketing
- Priority: P2 | Scope: Community | Sources: G
- Description: Emphasize "4,000 lines of Python" as a competitive advantage over bloated frameworks.
- Acceptance: Tagline and all marketing materials reference the lightweight codebase.

AC-161 | Add Research-Oriented Modules (CV / NLP / GenAI)
- Priority: P3 | Scope: Feature | Sources: G
- Description: Leverage the author's background to add specialized vision, NLP, and generative AI modules.
- Acceptance: Optional research extras provide advanced CV/NLP capabilities.

AC-162 | Add MLOps Features (Experiment Tracking, A/B Testing)
- Priority: P3 | Scope: Feature | Sources: G
- Description: Integrate experiment tracking for prompt variants and A/B test different agent configurations.
- Acceptance: Users can compare two prompt versions with statistical significance.

AC-163 | Add Comprehensive Inline Code Comments
- Priority: P2 | Scope: Quality | Sources: M
- Description: Explain reasoning behind complex functions, especially where prompts are constructed or security decisions are made.
- Acceptance: Every non-trivial function has a docstring explaining "why" not just "what".

AC-164 | Add Input Validation and Graceful Error Handling
- Priority: P1 | Scope: Quality | Sources: M
- Description: Validate all config inputs and API responses; catch timeouts, rate limits, and hallucinations with clear error messages.
- Acceptance: Invalid config fails fast with a helpful message; API timeouts retry with backoff.

---

Summary Statistics

Category	Count	P0	P1	P2	P3	
1. Repository Metadata & Discoverability	10	0	3	5	2	
2. Project Configuration, Packaging & Distribution	12	2	5	4	1	
3. Documentation & Developer Experience	15	0	6	7	2	
4. Testing, Code Quality & Maintainability	12	1	4	6	1	
5. Core Agent Architecture & Intelligence	11	0	6	4	1	
6. Memory, Knowledge & RAG Systems	13	0	7	5	1	
7. Multi-Modal Capabilities	7	0	4	2	1	
8. LLM Providers, Models & Routing	13	1	7	4	1	
9. MCP, Protocols & Tool Ecosystem	10	0	6	3	1	
10. Security, Safety & Compliance	13	3	7	2	1	
11. Observability, Evaluation & Tracing	8	0	4	4	0	
12. Deployment, Scaling & Infrastructure	12	0	4	7	1	
13. Channels, Integrations & Web UI	8	0	2	5	1	
14. Automation, Cron & Workflows	4	0	0	4	0	
15. Performance, Edge & Usability	6	0	1	3	2	
16. Community, Ecosystem & Adoption	11	0	3	4	4	
TOTAL	164	7	69	69	19	

---

Source Mapping Reference

- C-A1..A10 = Claude GitHub & Discoverability
- C-B11..B21 = Claude pyproject.toml
- C-C22..C27 = Claude Dockerfile
- C-D28..D32 = Claude CI / GitHub Actions
- C-E33..E51 = Claude Missing Features
- C-F52..F61 = Claude Documentation Gaps
- C-G62..G66 = Claude Security Issues
- K-1..10 = Kimi Memory & Knowledge
- K-11..19 = Kimi Agent Architecture
- K-20..25 = Kimi Multi-Modal
- K-26..28 = Kimi MCP & Protocols
- K-29..33 = Kimi Security
- K-34..37 = Kimi Observability
- K-38..48 = Kimi LLM Providers
- K-49..52 = Kimi Database & Infrastructure
- K-53..55 = Kimi Testing
- K-56..60 = Kimi Documentation
- K-61..62 = Kimi Local LLM
- G = Grok (grouped across 15 categories)
- M = Gemini (grouped across README, Core, Testing, Community)

---

End of Specification
