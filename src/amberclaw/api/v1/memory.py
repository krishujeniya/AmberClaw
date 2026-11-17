"""GDPR Memory Deletion and Right-to-be-Forgotten API Router."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from amberclaw.storage.tenant import (
    CrossTenantAccessViolationError,
    TenantContext,
    TenantIsolatedSessionDB,
)

router = APIRouter()
tenant_db = TenantIsolatedSessionDB(Path("data/tenants"))


class MemoryDeletionResponse(BaseModel):
    status: str
    message: str
    deleted_turns: int = 0


class GDPRExportResponse(BaseModel):
    export_id: str
    exported_at: str
    user_id: str | None = None
    session_id: str | None = None
    org_id: str | None = None
    schema_version: str = "2026.1.0"
    total_turns: int = 0
    turns: list[dict[str, Any]] = Field(default_factory=list)
    checksum_sha256: str


@router.get("/export", response_model=GDPRExportResponse)
async def export_gdpr_data(
    session_id: str | None = None,
    user_id: str | None = None,
    org_id: str | None = None,
) -> GDPRExportResponse:
    """Export stored user interaction records in portable format with SHA-256 integrity verification (GDPR Art. 15/20)."""
    active_tenant = TenantContext.get_current() or "default"
    if org_id and org_id != active_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access violation: caller from tenant '{active_tenant}' cannot access resources belonging to tenant '{org_id}'.",
        )
    try:
        export_payload = tenant_db.export_tenant_data(
            user_id=user_id,
            session_id=session_id,
            tenant_id=active_tenant,
        )
        return GDPRExportResponse(**export_payload)
    except CrossTenantAccessViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export user data: {e!s}",
        ) from e


@router.delete("/sessions/{session_id}", response_model=MemoryDeletionResponse)
async def delete_session_memory(session_id: str) -> MemoryDeletionResponse:
    """Permanently delete all stored interaction turns for a specific session ID within the tenant partition."""
    active_tenant = TenantContext.get_current() or "default"
    try:
        deleted_count = tenant_db.delete_session(session_id, tenant_id=active_tenant)
        return MemoryDeletionResponse(
            status="success",
            message=f"Session memory for '{session_id}' deleted successfully.",
            deleted_turns=deleted_count,
        )
    except CrossTenantAccessViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session memory: {e!s}",
        ) from e


@router.get("/sessions/{session_id}/turns")
async def get_session_turns(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve interaction turns for a specific session ID within tenant partition with pagination."""
    active_tenant = TenantContext.get_current() or "default"
    try:
        turns = tenant_db.get_turns(session_id=session_id, tenant_id=active_tenant)
        return turns[offset : offset + limit]
    except CrossTenantAccessViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.delete("/purge", response_model=MemoryDeletionResponse)
async def purge_all_user_memory() -> MemoryDeletionResponse:
    """Perform a complete Right-to-be-Forgotten purge scoped strictly to the calling tenant's partition."""
    active_tenant = TenantContext.get_current() or "default"
    try:
        deleted_count = tenant_db.purge_tenant_memory(tenant_id=active_tenant)
        return MemoryDeletionResponse(
            status="success",
            message="Right-to-be-forgotten memory purge completed successfully.",
            deleted_turns=deleted_count,
        )
    except CrossTenantAccessViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute memory purge: {e!s}",
        ) from e
