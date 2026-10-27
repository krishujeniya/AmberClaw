"""Chat and communication message schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    """Standard message roles in LLM chat conversations."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TextContentBlock(BaseModel):
    """Text block within a structured message."""

    type: str = "text"
    text: str


class ImageContentBlock(BaseModel):
    """Image URL/base64 block within a multimodal message."""

    type: str = "image_url"
    image_url: dict[str, str]


class ChatMessageSchema(BaseModel):
    """Pydantic model representing a single conversational message."""

    role: MessageRole
    content: str | list[TextContentBlock | ImageContentBlock | dict[str, Any]]
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InboundMessageSchema(BaseModel):
    """Schema for messages arriving from communication channels."""

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: str
    sender_id: str
    chat_id: str
    text: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutboundMessageSchema(BaseModel):
    """Schema for messages being dispatched to external communication channels."""

    recipient_id: str
    channel: str
    text: str
    reply_to_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
