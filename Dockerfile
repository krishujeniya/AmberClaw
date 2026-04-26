# Stage 1: Build dependencies
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set build environment
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Sync dependencies (including all extras)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --all-extras

# Copy source code
COPY . .

# Final sync to install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-extras

# Stage 2: Production image
FROM python:3.14-slim-bookworm AS final

# Set runtime environment
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    AMBERCLAW_HOME="/app/data"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment and app
COPY --from=builder /app /app

# Create data directory
RUN mkdir -p /app/data && chmod 777 /app/data

# Volume for persistent data
VOLUME ["/app/data"]

# Expose gateway port
EXPOSE 18790

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["amberclaw", "status"]

# Entrypoint
ENTRYPOINT ["amberclaw"]
CMD ["gateway"]
