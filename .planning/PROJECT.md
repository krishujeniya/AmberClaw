# AmberClaw

## What This Is

Unified, high-performance terminal agentic framework. A production-ready, terminal-native agentic system that unifies knowledge (RAG), data (VibeDS), and assistance (Council/Mythos) into a single, high-performance core.

## Core Value

Production-grade reliability and unified tool architecture for terminal-based AI agents.

## Requirements

### Validated

- ✓ **Unified Tool Registry**: Council, Mythos, and other features refactored into `PydanticTool` components.
- ✓ **Hatchling Build System**: Switched from legacy setup for better dependency management.
- ✓ **Clean Tool Architecture**: Property-based methods for Pydantic tools to ensure strict type-safety.

### Active

- [ ] **AmberClaw Doctor**: Implementation of system health check CLI command.
- [ ] **Async Data Operations**: Offloading Pandas I/O to background threads to prevent event loop blocking.
- [ ] **Parallel Tool Execution**: Run independent tool calls in `asyncio.TaskGroup`.
- [ ] **MCP Integration**: Support for external MCP servers.

### Out of Scope

- **Frontend/GUI**: Project is strictly terminal-native.
- **Legacy Streamlit**: All Streamlit dependencies removed and excluded.

## Context

The project has undergone a major unification phase. Legacy stubs were removed and features were refactored into a unified tool-registry pattern. It must run on Android (Termux), Linux, and Windows.

## Constraints

- **Tech Stack**: Python 3.11+, LiteLLM, Pydantic v2, Typer, Rich.
- **Environment**: Must remain performant in low-resource terminal environments.
- **Dependencies**: Minimize complex binary dependencies to ensure portability.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hatchling | Better support for modern Python packaging | ✓ Good |
| Pydantic v2 | Improved performance and validation | ✓ Good |
| Terminal-Native | Focus on developer productivity and speed | ✓ Good |

---
*Last updated: 2026-04-25 after GSD migration*
