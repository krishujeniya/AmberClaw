.PHONY: install dev check test build docker-build docker-up docker-down

# Variables
PYTHON := uv run python
PYTEST := uv run pytest
RUFF := uv run ruff

help:
	@echo "AmberClaw AI OS Makefile"
	@echo "========================"
	@echo "Usage:"
	@echo "  make install      Install the project and dependencies using uv"
	@echo "  make dev          Start the development server (API Gateway & OS Loop)"
	@echo "  make cli          Run the AmberClaw Typer CLI status check"
	@echo "  make check        Run formatters, linters, and type checkers"
	@echo "  make test         Run all tests (unit, integration, security)"
	@echo "  make docker-build Build the production Docker image"
	@echo "  make docker-up    Start the full stack (Gateway + ChromaDB) via Docker Compose"
	@echo "  make docker-down  Stop the full stack"

install:
	uv sync

dev:
	uv run amberclaw start --reload

cli:
	uv run amberclaw status

check:
	$(RUFF) check src/ tests/
	$(RUFF) format --check src/ tests/
	$(PYTHON) -m mypy src/

format:
	$(RUFF) check --fix src/ tests/
	$(RUFF) format src/ tests/

test:
	$(PYTEST) tests/

docker-build:
	docker build -t amberclaw/gateway:latest -f deploy/docker/Dockerfile .

docker-up:
	docker-compose -f deploy/docker/docker-compose.yml up -d

docker-down:
	docker-compose -f deploy/docker/docker-compose.yml down
