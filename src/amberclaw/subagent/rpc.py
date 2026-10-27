"""Inter-agent RPC protocol and message passing for subagent coordination."""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class RPCMessageType(StrEnum):
    """Types of messages transmitted across subagent communication channels."""

    REQUEST = "request"
    RESPONSE = "response"
    PROGRESS = "progress"
    NOTIFICATION = "notification"
    CANCEL = "cancel"
    ERROR = "error"


class RPCMessage(BaseModel):
    """Envelope for inter-subagent RPC messages and telemetry."""

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    correlation_id: str | None = Field(
        default=None, description="Request-response correlation ID"
    )
    source_id: str = Field(..., description="Sender agent or worker identifier")
    target_id: str = Field(..., description="Recipient agent or worker identifier")
    msg_type: RPCMessageType = Field(default=RPCMessageType.NOTIFICATION)
    method: str | None = Field(
        default=None, description="RPC method name if this is a request"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary message payload"
    )
    timestamp: float = Field(default_factory=time.time)


class SubagentRPCChannel:
    """Asynchronous, non-blocking in-memory message bus and RPC channel for subagents."""

    def __init__(self) -> None:
        self._handlers: dict[
            str, Callable[[RPCMessage], Awaitable[dict[str, Any] | None]]
        ] = {}
        self._pending_calls: dict[str, asyncio.Future[RPCMessage]] = {}
        self._history: list[RPCMessage] = []
        self._max_history = 500
        self._background_tasks: set[asyncio.Task[None]] = set()

    def register_handler(
        self,
        agent_id: str,
        handler: Callable[[RPCMessage], Awaitable[dict[str, Any] | None]],
    ) -> None:
        """Register an async message handler for a specific agent target."""
        self._handlers[agent_id] = handler

    def unregister_handler(self, agent_id: str) -> None:
        """Unregister the message handler for an agent."""
        self._handlers.pop(agent_id, None)

    async def notify(
        self,
        source_id: str,
        target_id: str,
        payload: dict[str, Any],
        msg_type: RPCMessageType = RPCMessageType.NOTIFICATION,
        method: str | None = None,
    ) -> RPCMessage:
        """Dispatch a one-way notification to a target agent."""
        msg = RPCMessage(
            source_id=source_id,
            target_id=target_id,
            msg_type=msg_type,
            method=method,
            payload=payload,
        )
        self._record_message(msg)

        handler = self._handlers.get(target_id)
        if handler:
            bg_task = asyncio.create_task(self._safe_dispatch(handler, msg))
            self._background_tasks.add(bg_task)
            bg_task.add_done_callback(self._background_tasks.discard)
        return msg

    async def call(
        self,
        source_id: str,
        target_id: str,
        method: str,
        params: dict[str, Any],
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Dispatch a synchronous RPC call and await response with correlation ID."""
        req_id = str(uuid.uuid4())[:12]
        loop = asyncio.get_running_loop()
        future: asyncio.Future[RPCMessage] = loop.create_future()
        self._pending_calls[req_id] = future

        msg = RPCMessage(
            message_id=req_id,
            correlation_id=req_id,
            source_id=source_id,
            target_id=target_id,
            msg_type=RPCMessageType.REQUEST,
            method=method,
            payload=params,
        )
        self._record_message(msg)

        handler = self._handlers.get(target_id)
        if not handler:
            self._pending_calls.pop(req_id, None)
            raise ConnectionError(
                f"No active RPC handler registered for target agent '{target_id}'"
            )

        bg_task = asyncio.create_task(self._safe_dispatch(handler, msg))
        self._background_tasks.add(bg_task)
        bg_task.add_done_callback(self._background_tasks.discard)

        try:
            response_msg = await asyncio.wait_for(future, timeout=timeout)
            if response_msg.msg_type == RPCMessageType.ERROR:
                err_msg = response_msg.payload.get("error", "Unknown RPC error")
                raise RuntimeError(
                    f"RPC call to '{target_id}.{method}' failed: {err_msg}"
                )
            return response_msg.payload
        finally:
            self._pending_calls.pop(req_id, None)

    async def respond(
        self,
        request_message: RPCMessage,
        payload: dict[str, Any],
        is_error: bool = False,
    ) -> RPCMessage:
        """Reply to an incoming RPC request using its correlation ID."""
        resp = RPCMessage(
            correlation_id=request_message.correlation_id or request_message.message_id,
            source_id=request_message.target_id,
            target_id=request_message.source_id,
            msg_type=RPCMessageType.ERROR if is_error else RPCMessageType.RESPONSE,
            payload=payload,
        )
        self._record_message(resp)

        corr_id = resp.correlation_id
        if corr_id and corr_id in self._pending_calls:
            fut = self._pending_calls[corr_id]
            if not fut.done():
                fut.set_result(resp)

        return resp

    async def send_progress(
        self,
        source_id: str,
        target_id: str,
        progress_pct: float,
        message: str = "",
    ) -> RPCMessage:
        """Send a lightweight task progress report."""
        return await self.notify(
            source_id=source_id,
            target_id=target_id,
            payload={"progress": progress_pct, "message": message},
            msg_type=RPCMessageType.PROGRESS,
        )

    def _record_message(self, msg: RPCMessage) -> None:
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    async def _safe_dispatch(
        self,
        handler: Callable[[RPCMessage], Awaitable[dict[str, Any] | None]],
        msg: RPCMessage,
    ) -> None:
        try:
            res = await handler(msg)
            if msg.msg_type == RPCMessageType.REQUEST and res is not None:
                await self.respond(msg, res)
        except Exception as exc:
            logger.error(
                "RPC handler exception for message {}: {}", msg.message_id, exc
            )
            if msg.msg_type == RPCMessageType.REQUEST:
                await self.respond(msg, {"error": str(exc)}, is_error=True)

    def get_history(self, limit: int = 50) -> list[RPCMessage]:
        """Return recently recorded messages."""
        return list(self._history[-limit:])
