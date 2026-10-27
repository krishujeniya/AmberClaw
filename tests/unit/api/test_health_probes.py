# ruff: noqa: PLR2004
"""Unit tests for API v1 health check, liveness, readiness, and startup probe endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from amberclaw.api.v1.health import router as health_router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(health_router, prefix="/api/v1/health")
    return TestClient(app)


def test_system_health_endpoint(client: TestClient):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["system"] == "AmberClaw AI OS"
    assert data["version"] == "2026.0.1"
    assert "uptime_seconds" in data
    assert "components" in data
    assert "config" in data["components"]
    assert "storage" in data["components"]
    assert "background_tasks" in data["components"]


def test_liveness_probe(client: TestClient):
    resp = client.get("/api/v1/health/liveness")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


def test_readiness_probe_healthy(client: TestClient):
    resp = client.get("/api/v1/health/readiness")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_startup_probe(client: TestClient):
    resp = client.get("/api/v1/health/startup")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"
    assert data["system"] == "AmberClaw AI OS"
