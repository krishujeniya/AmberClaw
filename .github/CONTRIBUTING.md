# Contributing to AmberClaw

Thanks for considering a contribution! Here is everything you need to know to get going.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Coding Standards](#coding-standards)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

All participants must follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

1. **Fork** this repository on GitHub.
2. **Clone** your fork:
   ```bash
   git clone https://github.com/<your-username>/AmberClaw.git
   cd AmberClaw
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/krishujeniya/AmberClaw.git
   ```

## Development Setup

### Prerequisites

- Python 3.11 or later
- [uv](https://github.com/astral-sh/uv) (preferred) or pip
- Git

### Installing dependencies

```bash
# With uv (preferred)
uv sync --all-extras --dev

# With pip
pip install -e ".[dev]"
```

### Verifying your setup

```bash
# Type checking
uv run pyright amberclaw

# Linting
uv run ruff check amberclaw

# Tests
uv run pytest
```

## Making Changes

1. **Branch off `main`**:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Write clear, focused commits.** Follow these prefixes:
   ```
   feat: add new provider integration
   fix: resolve memory leak in agent loop
   docs: update configuration guide
   refactor: simplify tool registry
   test: add unit tests for session manager
   chore: update dependencies
   ci: improve workflow caching
   ```

3. **Run quality checks before pushing**:
   ```bash
   uv run ruff check amberclaw
   uv run pyright amberclaw
   uv run pytest
   ```

## Coding Standards

### Python style

- Maximum line length is 100 characters.
- Target Python 3.11 and above.
- Format with [ruff](https://docs.astral.sh/ruff/).
- Type-check with [pyright](https://github.com/microsoft/pyright).
- Imports: standard library first, then third-party, then local. Use absolute imports.

### Type annotations

- Every public function must carry type hints.
- Use `from __future__ import annotations` where it helps.
- Prefer `X | None` over `Optional[X]`.

### Docstrings

- Every public module, class, and function needs a docstring.
- Use Google-style format:
  ```python
  def process(data: str, timeout: int = 30) -> dict[str, Any]:
      """Process incoming data within a timeout window.

      Args:
          data: Raw input string to process.
          timeout: Maximum wait time in seconds.

      Returns:
          Parsed result as a dictionary.

      Raises:
          ValueError: When data is empty.
      """
  ```

### Architecture principles

- Keep things ultra-lightweight — skip unnecessary abstractions.
- New tools must implement `BaseTool`.
- Providers must use the `ProviderSpec` registry pattern.
- Configuration lives in Pydantic models under `amberclaw/config/schema.py`.

## Submitting a Pull Request

1. **Push your branch**:
   ```bash
   git push origin feat/your-feature-name
   ```

2. **Open a PR** against `krishujeniya/AmberClaw:main`.

3. **Fill out the template**: summary, related issue, tests run, breaking changes.

4. **Wait for CI** — everything must go green before merging.

5. **Respond to review comments** quickly.

### PR checklist

- [ ] Follows project coding standards
- [ ] Passes type checking (pyright)
- [ ] Passes linting (ruff)
- [ ] Passes tests (pytest)
- [ ] Documentation updated where relevant
- [ ] No merge conflicts with main

## Reporting Issues

### Bugs

Open a [Bug Report](https://github.com/krishujeniya/AmberClaw/issues/new?template=bug_report.md) with:

- **Environment**: OS, Python version, AmberClaw version
- **Steps to reproduce**: minimal and clear
- **Expected vs actual behavior**
- **Logs**: relevant error output or stack traces

### Feature requests

Open a [Feature Request](https://github.com/krishujeniya/AmberClaw/issues/new?template=feature_request.md) explaining:

- The problem or limitation you hit
- Your proposed solution
- Alternatives you weighed

### Security issues

**Do not** file a public issue. Follow our [Security Policy](SECURITY.md) instead.

## License

Contributions fall under the [MIT License](LICENSE).
