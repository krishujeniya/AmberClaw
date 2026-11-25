# ruff: noqa: ASYNC240
"""FastAPI health check, liveness, readiness, and startup probe endpoints."""

import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from amberclaw.config.loader import get_config_path
from amberclaw.core.concurrency import TaskRegistry

router = APIRouter()

# OS startup timestamp
_STARTUP_TIME = time.time()


class ComponentStatus(BaseModel):
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    system: str = "AmberClaw AI OS"
    version: str = "2026.0.1"
    uptime_seconds: float
    components: dict[str, ComponentStatus] = Field(default_factory=dict)


@router.get("", response_model=HealthResponse)
async def system_health() -> HealthResponse:
    """Comprehensive health check of OS subsystems and background workers."""
    components: dict[str, ComponentStatus] = {}

    # 1. Config Check
    config_path = get_config_path()
    components["config"] = ComponentStatus(
        status="ok" if config_path.exists() else "degraded",
        details={"path": str(config_path), "exists": config_path.exists()},
    )

    # 2. Storage / State Store Check
    state_dir = Path("~/.amberclaw").expanduser()
    storage_ok = state_dir.exists() or os.access(state_dir.parent, os.W_OK)
    components["storage"] = ComponentStatus(
        status="ok" if storage_ok else "unhealthy",
        details={"path": str(state_dir), "writable": storage_ok},
    )

    # 3. Background Concurrency Registry Check
    active_tasks = TaskRegistry.get_instance().count()
    components["background_tasks"] = ComponentStatus(
        status="ok",
        details={"active_count": active_tasks},
    )

    overall_status = (
        "ok" if all(c.status == "ok" for c in components.values()) else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        uptime_seconds=round(time.time() - _STARTUP_TIME, 2),
        components=components,
    )


@router.get("/liveness")
async def liveness_probe() -> dict[str, str]:
    """Kubernetes liveness probe: indicates whether the process is alive."""
    return {"status": "alive"}


@router.get("/readiness")
async def readiness_probe(response: Response) -> dict[str, Any]:
    """Kubernetes readiness probe: indicates whether the OS is ready to serve traffic."""
    state_dir = Path("~/.amberclaw").expanduser()
    writable = state_dir.exists() or os.access(state_dir.parent, os.W_OK)

    if not writable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unready", "reason": "State storage directory not writable"}

    return {"status": "ready"}


@router.get("/startup")
async def startup_probe() -> dict[str, str]:
    """Kubernetes startup probe: indicates whether initialization has succeeded."""
    return {"status": "started", "system": "AmberClaw AI OS"}
