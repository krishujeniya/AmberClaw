"""GDPR Memory Deletion and Right-to-be-Forgotten API Router."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from amberclaw.memory.session_db import SessionDB

router = APIRouter()
session_db = SessionDB()


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
):
    """Export stored user interaction records in portable format with SHA-256 integrity verification (GDPR Art. 15/20)."""
    try:
        export_payload = session_db.export_user_data(
            user_id=user_id,
            session_id=session_id,
            org_id=org_id,
        )
        return GDPRExportResponse(**export_payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export user data: {e!s}",
        ) from e


@router.delete("/sessions/{session_id}", response_model=MemoryDeletionResponse)
async def delete_session_memory(session_id: str):
    """Permanently delete all stored interaction turns for a specific session ID (GDPR compliant)."""
    try:
        deleted_count = session_db.delete_session(session_id)
        return MemoryDeletionResponse(
            status="success",
            message=f"Session memory for '{session_id}' deleted successfully.",
            deleted_turns=deleted_count,
        )
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
):
    """Retrieve interaction turns for a specific session ID with pagination."""
    turns = session_db.get_turns(session_id=session_id)
    return turns[offset : offset + limit]


@router.delete("/purge", response_model=MemoryDeletionResponse)
async def purge_all_user_memory():
    """Perform a complete Right-to-be-Forgotten purge deleting all stored user session memory."""
    try:
        deleted_count = session_db.purge_all_sessions()
        return MemoryDeletionResponse(
            status="success",
            message="Right-to-be-forgotten memory purge completed successfully.",
            deleted_turns=deleted_count,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute memory purge: {e!s}",
        ) from e
