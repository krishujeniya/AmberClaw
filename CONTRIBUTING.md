# Contributing to AmberClaw

Thank you for your interest in contributing to AmberClaw! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Coding Standards](#coding-standards)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/AmberClaw.git
   cd AmberClaw
   ```
3. **Add** the upstream remote:
   ```bash
   git remote add upstream https://github.com/krishujeniya/AmberClaw.git
   ```

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git

### Install Dependencies

```bash
# Using uv (recommended)
uv sync --all-extras --dev

# Using pip
pip install -e ".[dev]"
```

### Verify Setup

```bash
# Run type checking
uv run pyright amberclaw

# Run linting
uv run ruff check amberclaw

# Run tests
uv run pytest
```

## Making Changes

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** with clear, focused commits.

3. **Follow the commit convention**:
   ```
   feat: add new provider integration
   fix: resolve memory leak in agent loop
   docs: update configuration guide
   refactor: simplify tool registry
   test: add unit tests for session manager
   chore: update dependencies
   ci: improve workflow caching
   ```

4. **Ensure quality** before pushing:
   ```bash
   uv run ruff check amberclaw
   uv run pyright amberclaw
   uv run pytest
   ```

## Coding Standards

### Python Style

- **Line length**: 100 characters max
- **Target version**: Python 3.11+
- **Formatter**: [ruff](https://docs.astral.sh/ruff/)
- **Type checker**: [pyright](https://github.com/microsoft/pyright)
- **Imports**: Use absolute imports; group stdlib → third-party → local

### Type Annotations

- All public functions **must** have type annotations
- Use `from __future__ import annotations` where appropriate
- Prefer `X | None` over `Optional[X]`

### Documentation

- All public modules, classes, and functions **must** have docstrings
- Use Google-style docstrings:
  ```python
  def process(data: str, timeout: int = 30) -> dict[str, Any]:
      """Process incoming data with timeout.

      Args:
          data: Raw input string to process.
          timeout: Maximum seconds to wait.

      Returns:
          Parsed result dictionary.

      Raises:
          ValueError: If data is empty.
      """
  ```

### Architecture Principles

- Keep the codebase **ultra-lightweight** — avoid unnecessary abstractions
- New tools must implement the `BaseTool` abstract class
- Providers must follow the `ProviderSpec` registry pattern
- Configuration uses Pydantic models in `amberclaw/config/schema.py`

## Submitting a Pull Request

1. **Push** your branch to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```

2. **Open a Pull Request** against `krishujeniya/AmberClaw:main`

3. **Fill in the PR template** with:
   - Summary of changes
   - Related issue (if any)
   - Testing done
   - Breaking changes (if any)

4. **Wait for CI** — all checks must pass before merge

5. **Address review feedback** promptly

### PR Checklist

- [ ] Code follows the project's coding standards
- [ ] Type checking passes (`pyright`)
- [ ] Linting passes (`ruff`)
- [ ] Tests pass (`pytest`)
- [ ] Documentation updated (if applicable)
- [ ] No merge conflicts with `main`

## Reporting Issues

### Bug Reports

Use the [Bug Report template](https://github.com/krishujeniya/AmberClaw/issues/new?template=bug_report.md) and include:

- **Environment**: OS, Python version, AmberClaw version
- **Steps to reproduce**: Clear, minimal reproduction steps
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Logs**: Relevant error output or stack traces

### Feature Requests

Use the [Feature Request template](https://github.com/krishujeniya/AmberClaw/issues/new?template=feature_request.md) and describe:

- **Problem**: What limitation or need does this address?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches you evaluated

### Security Vulnerabilities

**DO NOT** open a public issue. Follow the [Security Policy](SECURITY.md) for responsible disclosure.

## License

By contributing to AmberClaw, you agree that your contributions will be licensed under the [MIT License](LICENSE).
