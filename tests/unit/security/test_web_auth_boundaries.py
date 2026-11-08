"""The private dashboard must not expose data or simulate successful work."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.web.auth import WebAuthManager
from amberclaw.web.server import create_web_app


@pytest.mark.parametrize(
    "path",
    [
        "/api/dashboard/summary",
        "/api/sessions",
        "/api/governance/tickets",
        "/api/metrics/usage",
        "/api/audit/logs",
    ],
)
def test_anonymous_dashboard_reads_are_denied(path):
    response = TestClient(create_web_app()).get(path)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_anonymous_chat_is_denied():
    response = TestClient(create_web_app()).post(
        "/api/chat/stream", json={"message": "hello"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_missing_admin_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("WEB_ADMIN_USER", raising=False)
    monkeypatch.delenv("WEB_ADMIN_PASS", raising=False)
    assert not WebAuthManager().authenticate_credentials("admin", "amberclaw")


def test_no_default_login_cookie(monkeypatch):
    monkeypatch.delenv("WEB_ADMIN_USER", raising=False)
    monkeypatch.delenv("WEB_ADMIN_PASS", raising=False)
    response = TestClient(create_web_app()).post(
        "/api/web/login", json={"username": "admin", "password": "amberclaw"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not response.cookies
