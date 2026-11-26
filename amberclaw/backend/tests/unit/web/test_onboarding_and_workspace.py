# ruff: noqa: PLR2004
"""Unit tests for CL-017: Honest Onboarding, Workspace Readiness, and Run Controls."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from amberclaw.runtime.durable import (
    DurableExecutionCoordinator,
    DurableRun,
    DurableRunStore,
    DurableStep,
    RunStatus,
    StepStatus,
)
from amberclaw.web.auth import WebAuthManager
from amberclaw.web.server import create_web_app


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    monkeypatch.setenv("WEB_ADMIN_USER", "operator")
    monkeypatch.setenv("WEB_ADMIN_PASS", "sec-test-pass")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-mock-12345678901234567890")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = create_web_app(authentication=WebAuthManager())
    client = TestClient(app)

    # Log in
    login_res = client.post(
        "/api/web/login",
        json={"username": "operator", "password": "sec-test-pass"},
        headers={"Origin": "http://testserver"},
    )
    assert login_res.status_code == 200
    return client


def test_workspace_readiness_endpoint(auth_client):
    """Verify readiness reports real environment status and local model requirements without fabrication."""
    res = auth_client.get("/api/workspace/readiness")
    assert res.status_code == 200
    data = res.json()

    # ANTHROPIC was set in fixture, OPENAI was unset
    assert "ANTHROPIC" in data["configured_providers"]
    assert "OPENAI_API_KEY" in data["missing_credentials"]
    assert data["status"] == "ready"

    # Local model requirements must be explicitly documented
    assert "local_model_requirements" in data
    reqs = data["local_model_requirements"]
    assert "8 GB" in reqs["minimum_ram"]
    assert "qwen2.5:7b" in reqs["recommended_models"]
    assert reqs["recommended_context"] == "8,192 tokens"

    # Offline local service must remain visibly offline rather than fabricated as online
    assert data["local_model_status"] in {"offline", "available"}

    # Actionable recommendations present
    assert isinstance(data["recommendations"], list)


def test_workspace_artifacts_endpoint(auth_client, tmp_path, monkeypatch):
    """Verify live artifacts endpoint returns existing workspace files and metadata."""
    workspace_mock = tmp_path / ".amberclaw" / "workspace"
    workspace_mock.mkdir(parents=True, exist_ok=True)
    report_file = workspace_mock / "incident_report_2026.md"
    report_file.write_text("# Incident Summary\nResolved successfully.")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    res = auth_client.get("/api/workspace/artifacts")
    assert res.status_code == 200
    artifacts = res.json()

    assert len(artifacts) >= 1
    names = [a["name"] for a in artifacts]
    assert "incident_report_2026.md" in names
    item = next(a for a in artifacts if a["name"] == "incident_report_2026.md")
    assert item["size_bytes"] > 0
    assert "modified_at" in item


def test_run_cancellation_and_recovery_endpoints(auth_client, tmp_path):
    """Verify active runs can be cancelled and interrupted runs can be recovered."""
    db_file = tmp_path / "test_durable_web.db"
    store = DurableRunStore(db_path=db_file)
    DurableRunStore._instance = store

    # Create run
    run = store.create_run(
        tenant_id="tenant_web",
        workflow_name="web_orchestration",
        initial_input={"action": "test"},
    )
    step = store.create_step(
        run_id=run.run_id,
        step_index=0,
        action_type="long_running_task",
        idempotency_key="ik_web_0",
        is_side_effect=False,
    )
    store.mark_step_in_flight(step.step_id)

    # Cancel via API
    cancel_res = auth_client.post(
        f"/api/runs/{run.run_id}/cancel",
        json={"reason": "Operator requested emergency abort"},
    )
    assert cancel_res.status_code == 200
    c_data = cancel_res.json()
    assert c_data["status"] == "cancelled"
    assert c_data["run_id"] == run.run_id

    # Verify run updated in state machine
    updated = store.get_run(run.run_id)
    assert updated.status == RunStatus.FAILED

    # Recover via API
    recover_res = auth_client.post(f"/api/runs/{run.run_id}/recover", json={"strategy": "resume"})
    assert recover_res.status_code == 200
    r_data = recover_res.json()
    assert r_data["status"] == "recovered"
    assert r_data["report"]["run_id"] == run.run_id


def test_dashboard_html_accessibility_and_onboarding_elements():
    """Verify HTML template contains semantic onboarding banners, ARIA attributes, and artifacts."""
    html_path = Path(__file__).resolve().parents[3] / "src/amberclaw/web/static/index.html"
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    # Onboarding Readiness Banner
    assert 'id="readiness-panel"' in content
    assert 'aria-labelledby="readiness-title"' in content
    assert 'id="readiness-badge"' in content
    assert 'id="readiness-providers"' in content
    assert 'id="readiness-missing"' in content
    assert 'id="readiness-local-model"' in content

    # Live Workspace Artifacts & Controls
    assert 'id="workspace-artifacts-section"' in content
    assert 'id="artifacts-table-body"' in content
    assert 'id="btn-cancel-active-run"' in content
    assert 'id="btn-recover-last-run"' in content

    # WCAG 2.2 AA accessibility contracts
    assert 'class="skip-link"' in content
    assert ':focus-visible' in content
    assert 'role="dialog"' in content
    assert 'aria-live="polite"' in content


def test_dashboard_monochrome_tokens_and_reduced_motion():
    """Verify monochrome neutral tokens cover light/dark surfaces, states, and reduced motion."""
    html_path = (
        Path(__file__).resolve().parents[3] / "src/amberclaw/web/static/index.html"
    )
    content = html_path.read_text(encoding="utf-8")

    for token in (
        "--bg-base",
        "--bg-surface",
        "--bg-selected",
        "--bg-disabled",
        "--text-primary",
        "--text-muted",
        "--text-disabled",
        "--border",
        "--border-strong",
        "--border-selected",
        "--focus-ring",
    ):
        assert token in content

    assert "@media (prefers-color-scheme: light)" in content
    assert "@media (prefers-reduced-motion: reduce)" in content


def test_frontend_monochrome_tokens_and_reduced_motion():
    """Verify frontend/index.html uses monochrome neutral tokens with light/dark & reduced-motion support."""
    html_path = Path(__file__).resolve().parents[5] / "frontend" / "index.html"
    content = html_path.read_text(encoding="utf-8")

    for token in (
        "--bg-base",
        "--bg-surface",
        "--bg-elevated",
        "--bg-selected",
        "--bg-disabled",
        "--text-primary",
        "--text-secondary",
        "--text-muted",
        "--text-subtle",
        "--text-disabled",
        "--border",
        "--border-strong",
        "--border-selected",
        "--border-disabled",
        "--focus-ring",
    ):
        assert token in content

    assert "@media(prefers-color-scheme:light)" in content or "@media (prefers-color-scheme: light)" in content
    assert '[data-theme="light"]' in content
    assert "@media(prefers-reduced-motion:reduce)" in content or "@media (prefers-reduced-motion: reduce)" in content
    assert ":focus-visible" in content

    for legacy_amber in ("#efa955", "#ffcf8a", "#d9773f", "#100d0b"):
        assert legacy_amber not in content.lower()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
