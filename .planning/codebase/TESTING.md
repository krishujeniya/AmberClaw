# Testing

## Framework
- **Pytest**: Primary testing framework.
- **Pytest-asyncio**: For testing asynchronous core components.

## Structure
- `tests/`: Mirroring the package structure where appropriate.
- Covers:
  - Channels (Mocking platform APIs).
  - Loop (Verification of state and turns).
  - Tools (Individual function validation).
  - Config (Schema and path resolution).

## Commands
- Run all tests: `pytest`
- Run specific test: `pytest tests/test_loop_save_turn.py`

## Patterns
- Mocks are used heavily for LLMs and network calls.
- `docker-compose` support for integration testing (e.g., Matrix synapse).
