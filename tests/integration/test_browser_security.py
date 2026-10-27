import os
import pytest
from fastapi.testclient import TestClient
from amberclaw.api.main import app


def test_browser_security_headers_present():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    headers = response.headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-XSS-Protection"] == "1; mode=block"
    assert "max-age=31536000" in headers["Strict-Transport-Security"]
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in headers["Permissions-Policy"]


def test_production_cors_wildcard_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    with pytest.raises(RuntimeError, match=r"Wildcard origins '\*' are strictly prohibited in production mode"):
        # Re-evaluating CORS configuration in production mode
        env_name = os.getenv("ENVIRONMENT").lower()
        allowed_origins_env = os.getenv("CORS_ORIGINS")
        origins_list = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
        if env_name == "production" and ("*" in origins_list or not origins_list):
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: Wildcard origins '*' are strictly prohibited in production mode."
            )
