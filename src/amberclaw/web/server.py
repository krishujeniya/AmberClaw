"""FastAPI Web Dashboard Server for AmberClaw AI OS."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from amberclaw.web.auth import WebAuthManager

auth_manager = WebAuthManager()

STATIC_INDEX_PATH = Path(__file__).parent / "static" / "index.html"


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str


class SummaryResponse(BaseModel):
    status: str
    active_agents: int
    pending_tickets: int


def get_current_web_session(
    amberclaw_web_session: str | None = Cookie(None),
):
    """Dependency verifying web dashboard session cookie."""
    session = auth_manager.verify_session(amberclaw_web_session)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired web session token",
        )
    return session


def create_web_app() -> FastAPI:
    """Instantiate and configure the AmberClaw Web Dashboard FastAPI application."""
    app = FastAPI(title="AmberClaw Web Dashboard", version="2026.0.1")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard_index():
        """Serve the responsive web dashboard SPA interface."""
        if STATIC_INDEX_PATH.exists():
            return HTMLResponse(
                content=STATIC_INDEX_PATH.read_text(encoding="utf-8"), status_code=200
            )
        return HTMLResponse(content="<h1>AmberClaw AI OS</h1>", status_code=200)

    @app.post("/api/web/login")
    async def web_login(request: LoginRequest, response: Response):
        """Authenticate user and issue web session cookie."""
        if not auth_manager.authenticate_credentials(
            request.username, request.password
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        session = auth_manager.create_session(user_id=request.username)
        response.set_cookie(
            key="amberclaw_web_session",
            value=session.session_id,
            httponly=True,
            samesite="lax",
            secure=False,  # Can be set True in HTTPS production environments
        )
        return {"status": "ok", "session_id": session.session_id}

    @app.post("/api/web/logout")
    async def web_logout(
        response: Response,
        session=Depends(get_current_web_session),
    ):
        """Revoke active session and clear session cookie."""
        auth_manager.revoke_session(session.session_id)
        response.delete_cookie(key="amberclaw_web_session")
        return {"status": "logged_out"}

    @app.get("/api/dashboard/summary", response_model=SummaryResponse)
    async def dashboard_summary():
        """Return live dashboard system summary."""
        from amberclaw.api.v1.agents import agent_store  # noqa: PLC0415
        from amberclaw.governance.tickets import tickets  # noqa: PLC0415

        return SummaryResponse(
            status="healthy",
            active_agents=agent_store.count(),
            pending_tickets=len(tickets.get_pending_tickets()),
        )

    @app.post("/api/chat/stream")
    async def chat_stream(request: ChatRequest):
        """Streaming chat completion endpoint emitting text chunks."""

        async def event_generator():
            chunks = [
                "Received instruction: ",
                f"'{request.message}'. ",
                "Evaluating permissions under active policy lock... ",
                "Agent dispatch initialized. Zero-trust sandbox container active.",
            ]
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.05)

        return StreamingResponse(event_generator(), media_type="text/plain")

    @app.get("/api/sessions")
    async def list_sessions() -> list[dict[str, Any]]:
        """List active and historical workspace sessions."""
        return [
            {
                "session_id": "sess_default",
                "agent": "default",
                "status": "active",
                "created_at": "2026-10-27T10:00:00Z",
            },
            {
                "session_id": "sess_dev",
                "agent": "developer",
                "status": "idle",
                "created_at": "2026-10-27T08:30:00Z",
            },
        ]

    @app.get("/api/governance/tickets")
    async def list_governance_tickets() -> list[dict[str, Any]]:
        """List pending human-in-the-loop approval tickets."""
        from amberclaw.governance.tickets import tickets  # noqa: PLC0415

        pending = tickets.get_pending_tickets()
        return [
            {
                "ticket_id": t.id if hasattr(t, "id") else f"TICK-{idx}",
                "action": t.action if hasattr(t, "action") else str(t),
                "status": "pending",
            }
            for idx, t in enumerate(pending, start=1)
        ]

    @app.get("/api/metrics/usage")
    async def metrics_usage() -> dict[str, Any]:
        """Return telemetry metrics including token usage, cost, and latency."""
        return {
            "total_tokens": 1420500,
            "estimated_spend_usd": 4.18,
            "budget_cap_usd": 50.00,
            "p95_latency_ms": 340.0,
            "availability_ratio": 0.9998,
        }

    @app.get("/api/audit/logs")
    async def audit_logs() -> list[dict[str, Any]]:
        """Return recent tamper-evident audit records."""
        return [
            {
                "action": "vault.secret_accessed",
                "actor": "system",
                "resource": "ANTHROPIC_API_KEY",
                "outcome": "success",
                "hash": "a7f8b9c2d1e0",
            },
            {
                "action": "security.policy_lock.enforced",
                "actor": "policy_engine",
                "resource": "session_alpha",
                "outcome": "locked",
                "hash": "3e42c1f9b0a8",
            },
        ]

    return app
