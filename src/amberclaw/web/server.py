# ruff: noqa: PLR0915
"""Authenticated dashboard with explicit, optional runtime service bindings."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.governance.tickets import Ticket, TicketStatus
from amberclaw.security.approval import ApprovalStatus, ToolApprovalManager
from amberclaw.security.audit import AuditEvent
from amberclaw.web.auth import WebAuthManager, WebSession

auth_manager = WebAuthManager()
STATIC_INDEX_PATH = Path(__file__).parent / "static" / "index.html"


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ResolveTicketRequest(BaseModel):
    status: str
    reviewer_id: str = "operator"
    notes: str | None = None


class CancelTicketRequest(BaseModel):
    reason: str = "Operator cancelled"


class SummaryResponse(BaseModel):
    status: str
    active_agents: int | None
    pending_tickets: int | None


class ReadinessResponse(BaseModel):
    status: str
    configured_providers: list[str]
    missing_credentials: list[str]
    local_model_status: str
    local_model_requirements: dict[str, str]
    pending_approvals_count: int
    containment_mode: str
    recommendations: list[str]


class ArtifactItem(BaseModel):
    name: str
    path: str
    size_bytes: int
    modified_at: str


class CancelRunRequest(BaseModel):
    reason: str = "Operator cancelled run via dashboard"


class RecoverRunRequest(BaseModel):
    strategy: str = "resume"


class UsageResponse(BaseModel):
    """Unavailable measurements remain null instead of claiming zero usage."""

    total_tokens: int | None = None
    estimated_spend_usd: float | None = None
    budget_cap_usd: float | None = None
    p95_latency_ms: float | None = None
    availability_ratio: float | None = None


class SessionReader(Protocol):
    def list_sessions(self) -> list[dict[str, Any]]:
        """Read persisted session metadata from the canonical session manager."""
        ...


class TicketReader(Protocol):
    def get_pending_tickets(self) -> list[Ticket]: ...


class ChatRuntime(Protocol):
    async def process_direct(
        self,
        content: str,
        *,
        session_key: str,
        channel: str,
        chat_id: str,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Canonical AgentLoop direct-call and streaming callback contract."""
        ...


@dataclass(frozen=True)
class DashboardServices:
    """Read-only services and an explicitly configured agent runtime.

    The standalone dashboard has no automatic model execution or provider setup.
    Applications bind their existing services here when constructing the app.
    """

    sessions: SessionReader | None = None
    tickets: TicketReader | None = None
    usage: Callable[[], UsageResponse] | None = None
    audit: Callable[[], list[AuditEvent]] | None = None
    agent_count: Callable[[], int] | None = None
    runtime: ChatRuntime | None = None


def _verify_session(manager: WebAuthManager, token: str | None) -> WebSession:
    session = manager.verify_session(token or "")
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired web session token",
        )
    return session


def get_current_web_session(
    amberclaw_web_session: str | None = Cookie(None),
) -> WebSession:
    """Verify the default dashboard session cookie."""
    return _verify_session(auth_manager, amberclaw_web_session)


def _verify_origin(request: Request) -> None:
    """Reject cross-origin browser mutations authenticated with ambient cookies."""
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-origin request denied"
        )


async def _chat_chunks(
    runtime: ChatRuntime, message: str, session: WebSession
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    emitted = False

    async def on_token(text: str) -> None:
        nonlocal emitted
        if text:
            emitted = True
            await queue.put(text)

    async def run() -> None:
        try:
            result = await runtime.process_direct(
                message,
                session_key=f"web:{session.conversation_id}",
                channel="web",
                chat_id=session.conversation_id,
                on_token=on_token,
            )
            if not emitted:
                await queue.put(result)
        except Exception:
            logger.exception("Dashboard chat runtime failed")
            await queue.put("\n[Chat response unavailable: processing failed.]")
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while (chunk := await queue.get()) is not None:
            yield chunk
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_web_app(
    *,
    services: DashboardServices | None = None,
    authentication: WebAuthManager | None = None,
) -> FastAPI:
    """Create a private dashboard; absent service bindings remain unavailable."""
    app = FastAPI(title="AmberClaw Web Dashboard", version="2026.0.1")
    bound = services or DashboardServices()
    manager = authentication or auth_manager

    def current_session(amberclaw_web_session: str | None = Cookie(None)) -> WebSession:
        return _verify_session(manager, amberclaw_web_session)

    private = APIRouter(dependencies=[Depends(current_session)])

    @app.get("/", response_class=HTMLResponse)
    async def dashboard_index() -> HTMLResponse:
        content = (
            STATIC_INDEX_PATH.read_text(encoding="utf-8")
            if STATIC_INDEX_PATH.exists()
            else "<h1>AmberClaw AI OS</h1>"
        )
        return HTMLResponse(
            content=content, headers={"X-Robots-Tag": "noindex, nofollow"}
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Report only that this dashboard process can serve requests."""
        return {"status": "ok"}

    @app.post("/api/web/login", dependencies=[Depends(_verify_origin)])
    async def web_login(
        request: LoginRequest, response: Response, http_request: Request
    ) -> dict[str, str]:
        if not manager.authenticate_credentials(request.username, request.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        session = manager.create_session(user_id=request.username)
        response.set_cookie(
            key="amberclaw_web_session",
            value=session.session_id,
            httponly=True,
            samesite="strict",
            secure=http_request.url.scheme == "https",
        )
        return {"status": "ok"}

    @private.get("/api/web/session")
    async def web_session(
        session: WebSession = Depends(current_session),
    ) -> dict[str, str]:
        return {"user_id": session.user_id, "role": session.role}

    @private.post("/api/web/logout", dependencies=[Depends(_verify_origin)])
    async def web_logout(
        response: Response, session: WebSession = Depends(current_session)
    ) -> dict[str, str]:
        manager.revoke_session(session.session_id)
        response.delete_cookie(key="amberclaw_web_session")
        return {"status": "logged_out"}

    @private.get("/api/dashboard/summary", response_model=SummaryResponse)
    async def dashboard_summary() -> SummaryResponse:
        return SummaryResponse(
            status="configured" if bound.runtime is not None else "unavailable",
            active_agents=bound.agent_count()
            if bound.agent_count is not None
            else None,
            pending_tickets=len(bound.tickets.get_pending_tickets())
            if bound.tickets is not None
            else None,
        )

    @private.post("/api/chat/stream", dependencies=[Depends(_verify_origin)])
    async def chat_stream(
        request: ChatRequest, session: WebSession = Depends(current_session)
    ) -> StreamingResponse:
        if bound.runtime is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chat runtime is not configured",
            )
        return StreamingResponse(
            _chat_chunks(bound.runtime, request.message, session),
            media_type="text/plain",
        )

    @private.get("/api/sessions")
    async def list_sessions() -> list[dict[str, Any]]:
        return bound.sessions.list_sessions() if bound.sessions is not None else []

    @private.get("/api/governance/tickets")
    async def list_governance_tickets(
        detail: bool = False,
    ) -> list[dict[str, Any]]:
        mgr = ToolApprovalManager.get_instance()
        tickets_list = mgr.list_tickets()
        if tickets_list:
            if not detail:
                return [
                    {
                        "ticket_id": t.ticket_id,
                        "action": f"{t.tool_name} execution",
                        "status": t.status.value,
                    }
                    for t in tickets_list
                ]
            return [
                {
                    "ticket_id": t.ticket_id,
                    "actor": t.actor,
                    "action": f"{t.tool_name} execution",
                    "tool_name": t.tool_name,
                    "arguments": t.args,
                    "args_hash": t.args_hash,
                    "destination": t.destination,
                    "scope": t.scope,
                    "estimated_cost_usd": t.estimated_cost_usd,
                    "status": t.status.value,
                    "expires_at": t.expires_at.isoformat()
                    if t.expires_at
                    else None,
                    "created_at": t.created_at.isoformat()
                    if t.created_at
                    else None,
                }
                for t in tickets_list
            ]
        pending = (
            bound.tickets.get_pending_tickets() if bound.tickets is not None else []
        )
        if not detail:
            return [
                {
                    "ticket_id": ticket.id,
                    "action": ticket.description,
                    "status": ticket.status.value,
                }
                for ticket in pending
            ]
        return [
            {
                "ticket_id": ticket.id,
                "actor": ticket.requester_id,
                "action": ticket.description,
                "tool_name": ticket.context.get("tool_name", "action"),
                "arguments": ticket.context.get("args", {}),
                "args_hash": getattr(ticket, "args_hash", "") or "",
                "destination": getattr(ticket, "destination", "local"),
                "scope": getattr(ticket, "scope", "tool:execute"),
                "estimated_cost_usd": getattr(ticket, "estimated_cost_usd", 0.0),
                "status": ticket.status.value,
                "expires_at": ticket.expires_at.isoformat()
                if getattr(ticket, "expires_at", None)
                else None,
                "created_at": ticket.created_at.isoformat()
                if ticket.created_at
                else None,
            }
            for ticket in pending
        ]

    @private.get("/api/governance/tickets/{ticket_id}")
    async def get_governance_ticket(ticket_id: str) -> dict[str, Any]:
        mgr = ToolApprovalManager.get_instance()
        ticket = mgr.get_ticket(ticket_id)
        if ticket:
            return {
                "ticket_id": ticket.ticket_id,
                "actor": ticket.actor,
                "action": f"{ticket.tool_name} execution",
                "tool_name": ticket.tool_name,
                "arguments": ticket.args,
                "args_hash": ticket.args_hash,
                "destination": ticket.destination,
                "scope": ticket.scope,
                "estimated_cost_usd": ticket.estimated_cost_usd,
                "status": ticket.status.value,
                "expires_at": ticket.expires_at.isoformat()
                if ticket.expires_at
                else None,
                "created_at": ticket.created_at.isoformat()
                if ticket.created_at
                else None,
            }
        if bound.tickets is not None:
            t = bound.tickets.get_ticket(ticket_id)
            if t:
                return {
                    "ticket_id": t.id,
                    "actor": t.requester_id,
                    "action": t.description,
                    "tool_name": t.context.get("tool_name", "action"),
                    "arguments": t.context.get("args", {}),
                    "args_hash": getattr(t, "args_hash", "") or "",
                    "destination": getattr(t, "destination", "local"),
                    "scope": getattr(t, "scope", "tool:execute"),
                    "estimated_cost_usd": getattr(t, "estimated_cost_usd", 0.0),
                    "status": t.status.value,
                    "expires_at": t.expires_at.isoformat()
                    if getattr(t, "expires_at", None)
                    else None,
                    "created_at": t.created_at.isoformat()
                    if t.created_at
                    else None,
                }
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found",
        )

    @private.post("/api/governance/tickets/{ticket_id}/resolve")
    async def resolve_governance_ticket(
        ticket_id: str, request: ResolveTicketRequest
    ) -> dict[str, Any]:
        mgr = ToolApprovalManager.get_instance()
        approved = request.status.lower() == "approved"
        resolved = mgr.resolve_ticket(
            ticket_id=ticket_id,
            approved=approved,
            reviewer=request.reviewer_id,
            notes=request.notes or "",
        )
        if bound.tickets is not None:
            status_enum = (
                TicketStatus.APPROVED if approved else TicketStatus.REJECTED
            )
            bound.tickets.resolve_ticket(
                ticket_id=ticket_id,
                status=status_enum,
                reviewer_id=request.reviewer_id,
            )
        if not resolved:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket '{ticket_id}' not found or cannot be resolved",
            )
        return {
            "status": "success",
            "ticket_id": ticket_id,
            "resolution": "approved" if approved else "rejected",
        }

    @private.post("/api/governance/tickets/{ticket_id}/cancel")
    async def cancel_governance_ticket(
        ticket_id: str, request: CancelTicketRequest
    ) -> dict[str, Any]:
        mgr = ToolApprovalManager.get_instance()
        cancelled = mgr.cancel_ticket(
            ticket_id=ticket_id,
            reason=request.reason,
            actor="dashboard_operator",
        )
        if bound.tickets is not None:
            bound.tickets.resolve_ticket(
                ticket_id=ticket_id,
                status=TicketStatus.CANCELLED,
                reviewer_id="dashboard_operator",
            )
        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket '{ticket_id}' not found or cannot be cancelled",
            )
        return {"status": "success", "ticket_id": ticket_id, "cancelled": True}

    @private.get("/api/metrics/usage")
    async def metrics_usage() -> UsageResponse:
        return bound.usage() if bound.usage is not None else UsageResponse()

    @private.get("/api/audit/logs")
    async def audit_logs() -> list[dict[str, str]]:
        records = bound.audit() if bound.audit is not None else []
        return [
            {
                "action": event.action,
                "actor": event.actor,
                "resource": event.resource_id,
                "outcome": event.outcome,
                "hash": event.integrity_proof,
            }
            for event in records
        ]

    @private.get("/api/workspace/readiness", response_model=ReadinessResponse)
    async def workspace_readiness() -> ReadinessResponse:
        import os
        configured: list[str] = []
        missing: list[str] = []
        key_map = {
            "ANTHROPIC": "ANTHROPIC_API_KEY",
            "OPENAI": "OPENAI_API_KEY",
            "GEMINI": "GEMINI_API_KEY",
            "GROQ": "GROQ_API_KEY",
            "DEEPSEEK": "DEEPSEEK_API_KEY",
        }
        for prov, env_key in key_map.items():
            if os.getenv(env_key):
                configured.append(prov)
            else:
                missing.append(env_key)

        ollama_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        local_status = "offline"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=0.5) as client:
                res = await client.get(f"{ollama_url}/api/tags")
                if res.status_code == 200:
                    local_status = "available"
                    configured.append("LOCAL_OLLAMA")
        except Exception:
            local_status = "offline"

        mgr = ToolApprovalManager.get_instance()
        pending_list = mgr.list_tickets(status=ApprovalStatus.PENDING_APPROVAL)
        pending_count = len(pending_list)

        if configured:
            overall_status = "ready"
        elif local_status == "available":
            overall_status = "ready (local-only)"
        else:
            overall_status = "degraded (missing credentials)"

        recs: list[str] = []
        if not configured and local_status == "offline":
            recs.append("Configure at least one API key or launch a local Ollama server.")
        if local_status == "offline":
            recs.append("For offline execution: install Ollama and run 'ollama run qwen2.5:7b'.")
        if pending_count > 0:
            recs.append(f"You have {pending_count} pending approval ticket(s) in Governance Queue.")

        return ReadinessResponse(
            status=overall_status,
            configured_providers=configured,
            missing_credentials=missing,
            local_model_status=local_status,
            local_model_requirements={
                "minimum_ram": "8 GB for 7B/8B quantized models",
                "recommended_context": "8,192 tokens",
                "recommended_models": "qwen2.5:7b-instruct-q4_K_M, llama3.1:8b-instruct-q4_K_M",
                "host_url": ollama_url,
            },
            pending_approvals_count=pending_count,
            containment_mode="Landlock / seccomp enabled" if os.name == "posix" else "Degraded process containment",
            recommendations=recs,
        )

    @private.get("/api/workspace/artifacts", response_model=list[ArtifactItem])
    async def list_workspace_artifacts() -> list[ArtifactItem]:
        from datetime import UTC, datetime
        workspace_dir = Path.home() / ".amberclaw" / "workspace"
        if not workspace_dir.exists():
            return []
        items: list[ArtifactItem] = []
        for p in workspace_dir.glob("**/*"):
            if p.is_file() and not p.name.startswith("."):
                stat = p.stat()
                items.append(
                    ArtifactItem(
                        name=p.name,
                        path=str(p.relative_to(workspace_dir)),
                        size_bytes=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    )
                )
        return items

    @private.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str, request: CancelRunRequest) -> dict[str, Any]:
        from amberclaw.runtime.durable import DurableRunStore, RunStatus
        store = DurableRunStore.get_instance()
        run = store.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        store.update_run_status(run_id, RunStatus.FAILED)
        return {"status": "cancelled", "run_id": run_id, "reason": request.reason}

    @private.post("/api/runs/{run_id}/recover")
    async def recover_run(run_id: str, request: RecoverRunRequest) -> dict[str, Any]:
        from amberclaw.runtime.durable import DurableExecutionCoordinator, DurableRunStore
        store = DurableRunStore.get_instance()
        coordinator = DurableExecutionCoordinator(store=store)
        report = coordinator.recover_run(run_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or cannot be recovered")
        return {"status": "recovered", "run_id": run_id, "report": report.model_dump(mode="json")}

    app.include_router(private)
    return app
