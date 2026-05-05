# Conventions

## Coding Style
- **Python**: Standard PEP 8.
- **Typing**: Strict type hints required for all core components.
- **Docstrings**: Docstrings for all classes and major methods.
- **Logging**: Use `loguru` for structured logging. Avoid `print()` in core logic.

## Design Patterns
- **Pydantic Models**: All config, tools, and messages use Pydantic for validation.
- **Registry Pattern**: Tools and Providers use registries for dynamic lookup.
- **Dependency Injection**: `AgentLoop` receives its provider, bus, and workspace via constructor.
- **Composition over Inheritance**: Tools use composition with the `Tool` base class or `PydanticTool`.

## Tool Development
1. Define a Pydantic `BaseModel` for arguments.
2. Inherit from `PydanticTool`.
3. Implement `run()` (async).
4. Register in `AgentLoop._register_default_tools()`.

## Async/Await
- AmberClaw is **fully asynchronous**.
- Use `asyncio` for I/O and non-blocking tasks.
- CPU-bound data operations in `amberclaw.data` are wrapped or planned to be offloaded.
