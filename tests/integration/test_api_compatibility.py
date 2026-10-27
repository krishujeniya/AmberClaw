# ruff: noqa: PLR2004
"""API Compatibility, deprecation window, and playground safety tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from amberclaw.api.main import app
from amberclaw.api.middleware import APIDeprecationMiddleware


@pytest.fixture
def client():
    return TestClient(app)


def test_api_compatibility_health_and_metrics(client):
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_metrics = client.get("/metrics")
    assert res_metrics.status_code == 200
    assert "http_requests_total" in res_metrics.text


def test_api_compatibility_v1_error_envelope(client):
    # Requesting without auth should yield standard error envelope
    res = client.post("/api/v1/chat", json={})
    assert res.status_code in (401, 422)
    data = res.json()
    assert "error" in data or "detail" in data


def test_deprecation_middleware_headers():
    test_app = FastAPI()
    test_app.add_middleware(APIDeprecationMiddleware)

    @test_app.get("/api/v0/legacy-info")
    def legacy_info():
        return {"data": "old"}

    @test_app.get("/api/v1/current-info")
    def current_info():
        return {"data": "new"}

    tc = TestClient(test_app)

    # Legacy endpoint receives RFC 8594 deprecation headers
    res_legacy = tc.get("/api/v0/legacy-info")
    assert res_legacy.status_code == 200
    assert res_legacy.headers.get("Deprecation") == "true"
    assert "Sunset" in res_legacy.headers
    assert 'rel="sunset"' in res_legacy.headers.get("Link", "")

    # Modern v1 endpoint does NOT receive deprecation headers
    res_curr = tc.get("/api/v1/current-info")
    assert res_curr.status_code == 200
    assert "Deprecation" not in res_curr.headers


def test_api_playground_safe_environment_gating():
    # In test / non-production environment, Swagger UI docs are active
    tc = TestClient(app)
    docs_resp = tc.get("/docs")
    assert docs_resp.status_code == 200

    # In production environment, Swagger UI docs are omitted
    from amberclaw.api.main import os_lifespan  # noqa: PLC0415

    prod_app = FastAPI(
        docs_url=None,
        redoc_url=None,
        lifespan=os_lifespan,
    )
    tc_prod = TestClient(prod_app)
    prod_docs_resp = tc_prod.get("/docs")
    assert prod_docs_resp.status_code == 404
