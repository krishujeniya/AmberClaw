# Changelog

All notable changes to AmberClaw will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-25

### Added

- **Core Agent Framework**: Production-grade agentic loop with LLM ↔ tool execution
- **Multi-Provider Support**: OpenRouter, Anthropic, OpenAI, DeepSeek, Gemini, Groq, Azure OpenAI, vLLM, and more
- **Chat Integrations**: Telegram, Discord, WhatsApp, Feishu, DingTalk, Slack, Email, QQ, Matrix, Mochat
- **MCP Support**: Model Context Protocol for connecting external tool servers
- **Tool System**: Extensible tool registry with built-in exec, file, web, and spawn tools
- **Memory System**: Persistent conversation memory with knowledge base
- **Skills Framework**: Bundled and custom skill loading for agent specialization
- **Session Management**: Multi-session conversation support
- **Heartbeat System**: Periodic task execution via HEARTBEAT.md
- **Cron Jobs**: Scheduled task automation
- **Sub-Agent Spawning**: Background task execution with parallel agents
- **Docker Support**: Dockerfile and docker-compose for containerized deployment
- **Systemd Service**: Linux service configuration for production deployment
- **Multi-Instance**: Run multiple bots simultaneously with separate configs
- **OAuth Providers**: OpenAI Codex and GitHub Copilot via OAuth flow
- **Data Science Module**: EDA, ML pipelines, MLflow integration (optional)
- **Provider Registry**: Single-source-of-truth provider configuration system
- **CLI**: Full command-line interface via `typer` + `rich`
- **Type Safety**: Pyright type checking in CI pipeline
- **Security**: Path traversal protection, command filtering, allow-list access control

### Security

- Empty `allowFrom` now denies all access by default (use `["*"]` to allow all)
- WhatsApp bridge binds to localhost only with optional token auth
- Dangerous shell command patterns blocked by default
