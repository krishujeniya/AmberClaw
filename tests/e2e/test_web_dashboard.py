# ruff: noqa: PLR2004
"""End-to-End API and Web Dashboard tests for AmberClaw OS.

Validates:
1. Public health, liveness, readiness, and startup probes
2. Mandatory enterprise security response headers (CSP, HSTS, X-Frame-Options)
3. Prometheus metrics scraping endpoint (/metrics)
4. Authentication boundary on protected routes (401 on missing auth, 200 with JWT)
5. Governance ticket system lifecycle (create -> fetch -> resolve)
6. Dynamic skill registry and usage tracking endpoints
"""

from fastapi.testclient import TestClient

from amberclaw.api.auth import create_access_token
from amberclaw.api.main import app

client = TestClient(app)


def test_public_health_and_probes():
    # Root health
    res_root = client.get("/health")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "ok"

    # API v1 health
    res_v1_health = client.get("/api/v1/health")
    assert res_v1_health.status_code == 200
    assert res_v1_health.json()["status"] == "ok"

    # Liveness probe
    res_live = client.get("/api/v1/health/liveness")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    # Readiness probe
    res_ready = client.get("/api/v1/health/readiness")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"

    # Startup probe
    res_start = client.get("/api/v1/health/startup")
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "started"


def test_security_headers_enforcement():
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "max-age=" in headers["strict-transport-security"]
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_prometheus_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert len(response.text) > 0


def test_auth_guard_on_protected_endpoints():
    # Attempt unauthorized access to tickets
    res_unauth = client.get("/api/v1/tickets")
    assert res_unauth.status_code == 401
    assert "error" in res_unauth.json()

    # Valid JWT authentication
    token = create_access_token({"sub": "admin_test_user", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    res_auth = client.get("/api/v1/tickets", headers=headers)
    assert res_auth.status_code == 200
    assert isinstance(res_auth.json(), list)


def test_tickets_api_lifecycle():
    token = create_access_token({"sub": "ops_engineer", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a ticket
    create_payload = {
        "requester_id": "ops_engineer",
        "description": "Trigger automated read-replica scale up",
        "priority": "medium",
        "context": {"action": "db_scale_replica", "replicas": 3},
    }
    create_res = client.post("/api/v1/tickets/", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    ticket_data = create_res.json()
    ticket_id = ticket_data["id"]
    assert ticket_data["description"] == "Trigger automated read-replica scale up"
    assert ticket_data["status"] == "pending"

    # 2. Get ticket by ID
    get_res = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == ticket_id

    # 3. Resolve ticket (approval)
    resolve_payload = {
        "status": "approved",
        "reviewer_id": "sec_lead",
        "notes": "Capacity increase approved for peak traffic",
    }
    resolve_res = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        json=resolve_payload,
        headers=headers,
    )
    assert resolve_res.status_code == 200
    resolved_data = resolve_res.json()
    assert resolved_data["status"] == "success"
    assert resolved_data["resolution"] == "approved"

    # 4. Verify updated ticket status
    updated_get = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert updated_get.status_code == 200
    assert updated_get.json()["status"] == "approved"
    assert updated_get.json()["reviewer_id"] == "sec_lead"


def test_skills_api_lifecycle():
    token = create_access_token({"sub": "dev_user", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List skills
    list_res = client.get("/api/v1/skills/", headers=headers)
    assert list_res.status_code == 200
    assert isinstance(list_res.json(), list)

    # 2. Reload skills
    reload_res = client.post("/api/v1/skills/reload", headers=headers)
    assert reload_res.status_code == 200
    assert reload_res.json()["status"] == "success"
