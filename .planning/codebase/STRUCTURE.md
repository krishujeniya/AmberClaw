# Directory Structure

## Top-Level Layout
- `amberclaw/`: Main package
  - `agent/`: LLM orchestration and tools
    - `tools/`: Native feature implementations (Council, Mythos, Data, etc.)
  - `bus/`: Async message queue system
  - `channels/`: Messaging platform adapters
  - `cli/`: Command-line interface definitions (Typer)
  - `config/`: Pydantic schema and loader
  - `cron/`: Scheduled tasks and heartbeat
  - `data/`: Core logic for DataAgent (DS/ML agents)
  - `platforms/`: Platform-specific patches (Android/Linux)
  - `providers/`: LLM client abstractions
  - `skills/`: Prompt-based agent capabilities
  - `templates/`: Text templates for prompts and system messages
- `tests/`: Project test suite
- `.planning/`: GSD project management

## Key Files
- `amberclaw/__main__.py`: Module entry point (`python -m amberclaw`).
- `amberclaw/cli/commands.py`: Unified CLI implementation.
- `amberclaw/agent/loop.py`: Central agent execution logic.
- `pyproject.toml`: Dependencies and metadata.
- `README.md`: Documentation entry point.
