import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from amberclaw.api.middleware import RequestBodyLimitMiddleware, RateLimiterMiddleware


@pytest.fixture
def test_app():
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=1024 * 1024)  # 1 MB limit for test
    app.add_middleware(RateLimiterMiddleware, max_requests=3, window_seconds=60)  # 3 req/min for test

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/data")
    def post_data():
        return {"result": "success"}

    return app


def test_payload_size_limit_exceeded(test_app):
    client = TestClient(test_app)

    # Payload within limits (< 1 MB)
    resp = client.post("/data", json={"key": "val"}, headers={"content-length": "100"})
    assert resp.status_code == status.HTTP_200_OK

    # Payload exceeding limits (> 1 MB)
    resp_oversized = client.post(
        "/data", json={"key": "val"}, headers={"content-length": "2000000"}
    )
    assert resp_oversized.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert resp_oversized.json()["error"] == "Payload Too Large"


def test_rate_limiting_exceeded(test_app):
    client = TestClient(test_app)

    # 3 requests within limit
    for _ in range(3):
        resp = client.post("/data", json={"test": 1})
        assert resp.status_code == status.HTTP_200_OK

    # 4th request exceeds rate limit
    blocked = client.post("/data", json={"test": 1})
    assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert blocked.json()["error"] == "Too Many Requests"
    assert "Retry-After" in blocked.headers


def test_health_check_exempt_from_rate_limit(test_app):
    client = TestClient(test_app)

    # Health check should pass continuously without rate limiting
    for _ in range(10):
        resp = client.get("/health")
        assert resp.status_code == status.HTTP_200_OK
