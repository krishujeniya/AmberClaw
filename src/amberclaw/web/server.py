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

from amberclaw.governance.tickets import Ticket
from amberclaw.security.audit import AuditEvent
from amberclaw.web.auth import WebAuthManager, WebSession

auth_manager = WebAuthManager()
STATIC_INDEX_PATH = Path(__file__).parent / "static" / "index.html"


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class SummaryResponse(BaseModel):
    status: str
    active_agents: int | None
    pending_tickets: int | None


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
    async def list_governance_tickets() -> list[dict[str, str]]:
        pending = (
            bound.tickets.get_pending_tickets() if bound.tickets is not None else []
        )
        return [
            {
                "ticket_id": ticket.id,
                "action": ticket.description,
                "status": ticket.status.value,
            }
            for ticket in pending
        ]

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

    app.include_router(private)
    return app
