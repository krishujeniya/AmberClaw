# Changelog

Notable changes to AmberClaw are tracked here.

This file follows the conventions of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.1-alpha] - 2026-08-16

### Added
- **Zero-Trust Security Engine:** Linux Landlock process isolation, symlink escape boundary controls, and ExecTool dangerous command pattern filtering.
- **Cryptographic Audit Logger:** Structured append-only SHA-256 hash-chained JSONL security audit logger (`src/amberclaw/security/audit.py`) with secret and PII redactor.
- **Prometheus Telemetry & OpenAPI Spec:** `GET /metrics` Prometheus exposition endpoint, API request counters, token usage tracking, and OpenAPI 3.1.0 JSON contract exporter (`docs/openapi.json`).
- **FastAPI Web Dashboard SPA:** Dark glassmorphism web interface at `/` with cookie session authentication management (`src/amberclaw/web/server.py`).
- **GDPR Memory Deletion API:** Authenticated `DELETE /api/v1/memory/sessions/{session_id}` and right-to-be-forgotten `DELETE /api/v1/memory/purge` endpoints.
- **Reproducible Performance Benchmark Suite:** `benchmarks/benchmark_suite.py` measuring p50/p95/p99 latencies and throughput across secret scanning, audit logging, FTS5 search, and template rendering.
- **Workspace Template Engine & CLI Wizards:** `TemplateManager` prompt renderer, `amberclaw doctor` health diagnostic tool, and `amberclaw init` guided setup wizard.
- **Planning & RFC Discipline Structure:** Canonical `.planning/` directory structure with `PRODUCT_VISION.md`, `SECURITY_ROADMAP.md`, `TECHNICAL_DEBT.md`, `DEFINITION_OF_DONE.md`, and Architecture RFC Index (`RFC-001` through `RFC-005`).

### Security
- Replaced all pickle deserialization paths with Google Auth JSON format and JSON document storage.
- Enforced Bearer JWT / API Key authentication across all v1 routes (`/agents`, `/a2a`, `/tickets`, `/providers`, `/memory`).
- Hardened Docker Compose stack, Systemd service units, and Helm templates with non-root UID `10001:10001` and internal network isolation.
- Prohibited wildcard `*` CORS origins in production mode and injected HSTS, CSP, X-Frame-Options security headers.

## [1.0.0] - 2026-04-25

### Added

- Core agent framework with a production-grade agentic loop and LLM-to-tool execution pipeline
- Provider support for OpenRouter, Anthropic, OpenAI, DeepSeek, Gemini, Groq, Azure OpenAI, vLLM, and custom endpoints
- Chat platform integrations: Telegram, Discord, WhatsApp, Feishu, DingTalk, Slack, Email, QQ, Matrix, Mochat
- Model Context Protocol (MCP) for connecting external tool servers
- Extensible tool system with a registry plus built-in exec, file, web, and spawn tools
- Persistent memory system with a conversation-scoped knowledge base
- Skills framework supporting both bundled and user-defined skill files
- Session management for multiple concurrent conversations
- Heartbeat system that executes periodic tasks defined in HEARTBEAT.md
- Cron-based scheduled task automation
- Sub-agent spawning for background and parallel work
- Dockerfile and docker-compose configuration for containerized deployments
- Systemd unit file for running as a Linux service
- Multi-instance support — run several bots at once with separate configs
- OAuth login for OpenAI Codex and GitHub Copilot providers
- Optional data science module with EDA, ML pipelines, and MLflow
- Provider registry acting as single source of truth for all LLM backends
- Full CLI built on typer and rich
- Pyright type checking enforced in CI
- Security hardening: path traversal guards, command pattern filtering, allow-list access control

### Security

- An empty `allowFrom` list now blocks all access by default (set `["*"]` to open it up)
- WhatsApp bridge binds exclusively to localhost, with optional token-based auth
- Known dangerous shell patterns are blocked out of the box
