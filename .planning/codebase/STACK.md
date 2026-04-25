# Stack

## Overview
AmberClaw is a Python-based agentic framework designed for terminal-native productivity and high-performance cross-platform support (Android/Linux/Windows).

## Core Technologies
- **Language**: Python >= 3.11
- **CLI Framework**: [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/)
- **LLM Proxy**: [LiteLLM](https://docs.litellm.ai/) (Unified API for 100+ providers)
- **Agent Framework**: [LangChain](https://www.langchain.com/) + [LangGraph](https://langchain-ai.github.io/langgraph/) (partial usage for complex flows)
- **Schema & Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Configuration**: [Pydantic Settings](https://docs.pydantic.dev/latest/usage/pydantic_settings/)

## Key Dependencies
- `litellm`: Multi-model orchestration
- `typer`: CLI command structure
- `rich`: Terminal UI and log formatting
- `loguru`: Structured logging
- `pydantic`: Type safety and tool schemas
- `websockets`: Real-time chat channel support
- `python-telegram-bot`, `slack-sdk`, `discord.py`: Messaging integrations
- `pandas`, `plotly`, `scikit-learn`: DataAgent tools

## Build System
- [Hatchling](https://hatch.pypa.io/): Build backend
- [uv](https://github.com/astral-sh/uv): Fast dependency resolution and lock management
- `pyproject.toml`: Modern project specification

## Deployment
- Terminal-only execution
- Server mode for multi-channel support
- Docker support for isolated environments
