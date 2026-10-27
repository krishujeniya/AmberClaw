# ruff: noqa: PLR2004
"""Unit tests for AmberClaw Skills API endpoints and lifecycle management."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from amberclaw.api.v1.skills import (
    get_skill_registry,
    get_skill_scanner,
    get_skill_tracker,
)
from amberclaw.api.v1.skills import (
    router as skills_router,
)
from amberclaw.skills.format import serialize_skill_markdown
from amberclaw.skills.skill import SkillDefinition, SkillMetadata


@pytest.fixture(autouse=True)
def clean_skills_state():
    """Reset registry and tracker before and after each test."""
    registry = get_skill_registry()
    tracker = get_skill_tracker()

    # Register standard test fixture skills
    registry._skills.clear()
    tracker.metrics.clear()

    s1 = SkillDefinition(
        metadata=SkillMetadata(
            name="code-reviewer",
            version="1.0.0",
            description="Reviews code for security and performance vulnerabilities",
            author="amberclaw-core",
            tags=["code", "security", "review"],
            is_enabled=True,
        ),
        instructions="# Code Reviewer\nReview pull requests meticulously.",
    )
    s2 = SkillDefinition(
        metadata=SkillMetadata(
            name="rag-query-enhancer",
            version="2.1.0",
            description="Expands and rewrites queries for hybrid vector search",
            author="search-team",
            tags=["rag", "search", "nlp"],
            is_enabled=True,
        ),
        instructions="# RAG Enhancer\nGenerate keyword synonyms.",
    )

    registry.register(s1)
    registry.register(s2)

    yield

    registry._skills.clear()
    tracker.metrics.clear()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(skills_router, prefix="/api/v1/skills")
    return TestClient(app)


# ==============================================================================
# 1. Listing & Searching Skills
# ==============================================================================


def test_list_skills_returns_all(client: TestClient):
    resp = client.get("/api/v1/skills")
    assert resp.status_code == 200
    skills = resp.json()
    assert len(skills) == 2
    names = [s["name"] for s in skills]
    assert "code-reviewer" in names
    assert "rag-query-enhancer" in names


def test_list_skills_filter_by_query_and_tag(client: TestClient):
    # Search by keyword
    resp_q = client.get("/api/v1/skills?q=vulnerabilities")
    assert resp_q.status_code == 200
    data_q = resp_q.json()
    assert len(data_q) == 1
    assert data_q[0]["name"] == "code-reviewer"

    # Filter by tag
    resp_tag = client.get("/api/v1/skills?tag=search")
    assert resp_tag.status_code == 200
    data_tag = resp_tag.json()
    assert len(data_tag) == 1
    assert data_tag[0]["name"] == "rag-query-enhancer"

    # Filter with non-matching tag
    resp_empty = client.get("/api/v1/skills?tag=nonexistent_tag_xyz")
    assert resp_empty.status_code == 200
    assert len(resp_empty.json()) == 0


# ==============================================================================
# 2. Skill Details
# ==============================================================================


def test_get_skill_details_success(client: TestClient):
    resp = client.get("/api/v1/skills/code-reviewer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["name"] == "code-reviewer"
    assert data["metadata"]["version"] == "1.0.0"
    assert "Review pull requests" in data["instructions"]


def test_get_skill_details_not_found(client: TestClient):
    resp = client.get("/api/v1/skills/unknown-skill-404")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ==============================================================================
# 3. Enable / Disable Lifecycle
# ==============================================================================


def test_enable_and_disable_lifecycle(client: TestClient):
    # Disable skill
    resp_dis = client.post("/api/v1/skills/code-reviewer/disable")
    assert resp_dis.status_code == 200
    assert resp_dis.json()["is_enabled"] is False

    # Check listed skills with enabled_only=True
    resp_enabled = client.get("/api/v1/skills?enabled_only=true")
    assert resp_enabled.status_code == 200
    names = [s["name"] for s in resp_enabled.json()]
    assert "code-reviewer" not in names
    assert "rag-query-enhancer" in names

    # Re-enable skill
    resp_en = client.post("/api/v1/skills/code-reviewer/enable")
    assert resp_en.status_code == 200
    assert resp_en.json()["is_enabled"] is True

    # Confirm it is enabled again
    resp_check = client.get("/api/v1/skills/code-reviewer")
    assert resp_check.json()["metadata"]["is_enabled"] is True


def test_enable_disable_non_existent(client: TestClient):
    resp1 = client.post("/api/v1/skills/ghost_skill/enable")
    assert resp1.status_code == 404

    resp2 = client.post("/api/v1/skills/ghost_skill/disable")
    assert resp2.status_code == 404


# ==============================================================================
# 4. Reload from Filesystem
# ==============================================================================


def test_reload_skills_discovers_new_skill(client: TestClient, tmp_path: Path):
    custom_skills_dir = tmp_path / "custom_skills"
    custom_skills_dir.mkdir()

    new_skill_dir = custom_skills_dir / "cloud-architect"
    new_skill_dir.mkdir()

    meta = SkillMetadata(
        name="cloud-architect",
        version="1.0.0",
        description="Generates Terraform and AWS CloudFormation architecture",
        tags=["terraform", "aws", "infra"],
    )
    instructions = "# Cloud Architect\nDesign resilient distributed architectures."
    (new_skill_dir / "SKILL.md").write_text(
        serialize_skill_markdown(meta, instructions),
        encoding="utf-8",
    )

    scanner = get_skill_scanner()
    scanner.add_search_path(custom_skills_dir)

    resp = client.post("/api/v1/skills/reload")
    assert resp.status_code == 200
    assert "cloud-architect" in resp.json()["skills"]

    # Verify newly discovered skill is retrievable
    resp_get = client.get("/api/v1/skills/cloud-architect")
    assert resp_get.status_code == 200
    assert resp_get.json()["metadata"]["name"] == "cloud-architect"


# ==============================================================================
# 5. Usage Telemetry & Metrics
# ==============================================================================


def test_skill_usage_recording_and_metrics(client: TestClient):
    # Initial metrics empty
    resp_init = client.get("/api/v1/skills/code-reviewer/metrics")
    assert resp_init.status_code == 200
    assert resp_init.json()["invocations"] == 0

    # Record 1st execution
    resp_rec1 = client.post(
        "/api/v1/skills/code-reviewer/record-usage",
        json={"duration_ms": 120.5, "success": True},
    )
    assert resp_rec1.status_code == 200
    assert resp_rec1.json()["invocations"] == 1
    assert resp_rec1.json()["success_rate"] == 1.0

    # Record 2nd execution (failed)
    resp_rec2 = client.post(
        "/api/v1/skills/code-reviewer/record-usage",
        json={"duration_ms": 79.5, "success": False},
    )
    assert resp_rec2.status_code == 200
    assert resp_rec2.json()["invocations"] == 2
    assert resp_rec2.json()["failures"] == 1
    assert resp_rec2.json()["success_rate"] == 0.5
    assert resp_rec2.json()["avg_execution_time_ms"] == 100.0

    # Verify metrics endpoint reflects updated statistics
    resp_metrics = client.get("/api/v1/skills/code-reviewer/metrics")
    assert resp_metrics.status_code == 200
    assert resp_metrics.json()["invocations"] == 2
