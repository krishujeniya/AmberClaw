import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.web.auth import WebAuthManager
from amberclaw.web.server import create_web_app


@pytest.fixture
def client():
    app = create_web_app()
    return TestClient(app)


def test_dashboard_html_rendering(client):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "<title>AmberClaw AI OS" in response.text
    assert "AmberClaw Mission Control" in response.text
    assert 'dialog id="approval-dialog"' in response.text


def test_dashboard_summary_api(client):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "active_agents" in data
    assert "pending_tickets" in data


def test_dashboard_extended_apis(client):
    # Chat streaming endpoint
    stream_resp = client.post("/api/chat/stream", json={"message": "hello"})
    assert stream_resp.status_code == status.HTTP_200_OK
    assert "Received instruction" in stream_resp.text

    # Sessions endpoint
    sess_resp = client.get("/api/sessions")
    assert sess_resp.status_code == status.HTTP_200_OK
    assert isinstance(sess_resp.json(), list)

    # Governance tickets endpoint
    gov_resp = client.get("/api/governance/tickets")
    assert gov_resp.status_code == status.HTTP_200_OK
    assert isinstance(gov_resp.json(), list)

    # Metrics endpoint
    met_resp = client.get("/api/metrics/usage")
    assert met_resp.status_code == status.HTTP_200_OK
    assert "total_tokens" in met_resp.json()

    # Audit logs endpoint
    aud_resp = client.get("/api/audit/logs")
    assert aud_resp.status_code == status.HTTP_200_OK
    assert isinstance(aud_resp.json(), list)


def test_web_auth_login_flow(client):
    # Bad login
    bad_resp = client.post(
        "/api/web/login",
        json={"username": "admin", "password": "wrong_password"},
    )
    assert bad_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Valid login
    good_resp = client.post(
        "/api/web/login",
        json={"username": "admin", "password": "amberclaw"},
    )
    assert good_resp.status_code == status.HTTP_200_OK
    assert "amberclaw_web_session" in good_resp.cookies
    session_id = good_resp.cookies["amberclaw_web_session"]

    # Logout
    client.cookies.set("amberclaw_web_session", session_id)
    logout_resp = client.post("/api/web/logout")
    assert logout_resp.status_code == status.HTTP_200_OK


def test_web_auth_manager_direct():
    mgr = WebAuthManager()
    assert mgr.authenticate_credentials("admin", "amberclaw")
    assert not mgr.authenticate_credentials("admin", "invalid")

    session = mgr.create_session("admin")
    assert mgr.verify_session(session.session_id) is not None
    mgr.revoke_session(session.session_id)
    assert mgr.verify_session(session.session_id) is None
