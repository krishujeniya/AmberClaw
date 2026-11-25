"""FastAPI routes for Skills discovery, lifecycle management, and runtime metrics."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger
from amberclaw.skills.registry import SkillRegistry
from amberclaw.skills.scanner import SkillScanner
from amberclaw.skills.skill import SkillDefinition, SkillMetadata
from amberclaw.skills.tracker import SkillUsageMetric, SkillUsageTracker

router = APIRouter()

# Global default instances for runtime skill management
_default_registry = SkillRegistry()
_default_tracker = SkillUsageTracker()
_default_scanner = SkillScanner()

# Default skill directories to scan
_default_skills_dir = Path(__file__).resolve().parents[2] / "skills"
if _default_skills_dir.exists():
    _default_scanner.add_search_path(_default_skills_dir)


def get_skill_registry() -> SkillRegistry:
    return _default_registry


def get_skill_tracker() -> SkillUsageTracker:
    return _default_tracker


def get_skill_scanner() -> SkillScanner:
    return _default_scanner


def reload_skills() -> list[SkillDefinition]:
    """Discover all skills on search paths and sync into the active registry."""
    scanner = get_skill_scanner()
    registry = get_skill_registry()
    discovered = scanner.scan()
    for s in discovered:
        # Preserve user-configured enabled status if already registered
        existing = registry.get(s.name)
        if existing and not existing.is_enabled:
            s.metadata.is_enabled = False
        registry.register(s)
    return discovered


# Initial discovery on import
reload_skills()


# ==============================================================================
# Request & Response Schemas
# ==============================================================================


class SkillSummary(BaseModel):
    name: str
    version: str
    description: str
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_enabled: bool


class SkillDetailResponse(BaseModel):
    metadata: SkillMetadata
    instructions: str
    directory_path: str | None = None
    metrics: SkillUsageMetric | None = None


class RecordUsageRequest(BaseModel):
    duration_ms: float = Field(
        ..., ge=0.0, description="Execution duration in milliseconds"
    )
    success: bool = Field(default=True, description="Whether execution was successful")


# ==============================================================================
# Endpoints
# ==============================================================================


@router.get("", response_model=list[SkillSummary])
async def list_skills(
    enabled_only: bool = Query(False, description="Filter for enabled skills only"),
    q: str | None = Query(None, description="Keyword search query"),
    tag: str | None = Query(None, description="Filter by specific tag"),
) -> list[SkillSummary]:
    """List registered skills with optional search and filtering."""
    registry = get_skill_registry()

    skills = registry.search(q) if q else registry.list_all(enabled_only=enabled_only)

    if tag:
        tag_lower = tag.lower()
        skills = [
            s for s in skills if any(tag_lower == t.lower() for t in s.metadata.tags)
        ]

    return [
        SkillSummary(
            name=s.name,
            version=s.metadata.version,
            description=s.metadata.description,
            author=s.metadata.author,
            tags=s.metadata.tags,
            is_enabled=s.is_enabled,
        )
        for s in skills
    ]


@router.get("/{skill_name}", response_model=SkillDetailResponse)
async def get_skill_details(skill_name: str) -> SkillDetailResponse:
    """Retrieve full skill definition, documentation, and telemetry."""
    registry = get_skill_registry()
    skill = registry.get(skill_name)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found",
        )

    tracker = get_skill_tracker()
    metric = tracker.get_metric(skill_name)

    return SkillDetailResponse(
        metadata=skill.metadata,
        instructions=skill.instructions,
        directory_path=str(skill.directory_path) if skill.directory_path else None,
        metrics=metric,
    )


@router.post("/{skill_name}/enable")
async def enable_skill(skill_name: str) -> dict[str, Any]:
    """Enable a skill for agent discovery and execution."""
    registry = get_skill_registry()
    success = registry.set_enabled(skill_name, True)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found",
        )

    audit_logger = SecurityAuditLogger.get_logger()
    audit_logger.log_event(
        AuditEvent(
            actor="operator",
            action="skill.enabled",
            resource_type="skill",
            resource_id=skill_name,
            outcome="success",
        )
    )

    return {"status": "success", "skill_name": skill_name, "is_enabled": True}


@router.post("/{skill_name}/disable")
async def disable_skill(skill_name: str) -> dict[str, Any]:
    """Disable a skill, preventing agents from discovering or using it."""
    registry = get_skill_registry()
    success = registry.set_enabled(skill_name, False)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found",
        )

    audit_logger = SecurityAuditLogger.get_logger()
    audit_logger.log_event(
        AuditEvent(
            actor="operator",
            action="skill.disabled",
            resource_type="skill",
            resource_id=skill_name,
            outcome="success",
        )
    )

    return {"status": "success", "skill_name": skill_name, "is_enabled": False}


@router.post("/reload")
async def trigger_skills_reload() -> dict[str, Any]:
    """Rescan registered search paths and reload skill definitions."""
    discovered = reload_skills()
    skill_names = [s.name for s in discovered]

    audit_logger = SecurityAuditLogger.get_logger()
    audit_logger.log_event(
        AuditEvent(
            actor="operator",
            action="skills.reloaded",
            resource_type="skill_registry",
            resource_id="global",
            outcome="success",
            metadata={"count": len(skill_names)},
        )
    )

    return {
        "status": "success",
        "discovered_count": len(skill_names),
        "skills": skill_names,
    }


@router.get("/{skill_name}/metrics", response_model=SkillUsageMetric)
async def get_skill_metrics(skill_name: str) -> SkillUsageMetric:
    """Retrieve runtime usage metrics and health for a skill."""
    registry = get_skill_registry()
    if not registry.get(skill_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found",
        )

    tracker = get_skill_tracker()
    metric = tracker.get_metric(skill_name)
    if not metric:
        return SkillUsageMetric(skill_name=skill_name)
    return metric


@router.post("/{skill_name}/record-usage", response_model=SkillUsageMetric)
async def record_skill_usage(
    skill_name: str, payload: RecordUsageRequest
) -> SkillUsageMetric:
    """Record a telemetry execution event for a skill."""
    registry = get_skill_registry()
    if not registry.get(skill_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found",
        )

    tracker = get_skill_tracker()
    return tracker.record_execution(
        skill_name=skill_name,
        duration_ms=payload.duration_ms,
        success=payload.success,
    )
