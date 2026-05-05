# syntax=docker/dockerfile:1.4
FROM python:3.11-slim as builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set up environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-install-project --no-dev

# ---------------------------------------------------
FROM python:3.11-slim as runtime

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r amberclaw && useradd -r -g amberclaw amberclaw

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder --chown=amberclaw:amberclaw /app/.venv /app/.venv

# Ensure the venv is in the path
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application code
COPY --chown=amberclaw:amberclaw src/ ./src/
COPY --chown=amberclaw:amberclaw pyproject.toml ./

# Install the project itself (without reinstalling dependencies)
RUN uv pip install -e . --no-deps

# Switch to non-root user
USER amberclaw

# Expose the API port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["amberclaw", "start", "--host", "0.0.0.0", "--port", "8000"]
