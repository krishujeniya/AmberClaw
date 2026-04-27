# Changelog

Notable changes to AmberClaw are tracked here.

This file follows the conventions of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Prepared documentation site structure (MkDocs)
- Added API reference using mkdocstrings
- Expanded README with comparison tables and extra instructions
- Added examples directory and sample configurations

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
