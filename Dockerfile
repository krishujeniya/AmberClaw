# syntax=docker/dockerfile:1.4
# Stage 1: Build virtualenv using uv
FROM python:3.15-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md THIRD_PARTY_NOTICES.md ./

RUN uv sync --frozen --no-install-project --no-dev

# Stage 2: Minimal hardened runtime image
FROM python:3.15-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/uv

RUN groupadd -r amberclaw -g 1001 && \
    useradd -r -u 1001 -g amberclaw -m -s /bin/bash amberclaw

WORKDIR /app

COPY --from=builder --chown=amberclaw:amberclaw /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AMBERCLAW_HOST=0.0.0.0 \
    AMBERCLAW_PORT=8000

COPY --chown=amberclaw:amberclaw src/ ./src/
COPY --chown=amberclaw:amberclaw pyproject.toml README.md THIRD_PARTY_NOTICES.md ./

RUN uv pip install -e . --no-deps

USER amberclaw

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["amberclaw"]
CMD ["start", "--host", "0.0.0.0", "--port", "8000"]
