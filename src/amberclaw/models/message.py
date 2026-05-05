"""
AmberClaw Message Models
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """Model for a tool call from the LLM."""
    id: str
    type: str = "function"
    function: dict[str, Any]


class ToolResult(BaseModel):
    """Result of a tool execution."""
    tool_call_id: str
    output: str
    error: str | None = None


class Message(BaseModel):
    """Unified message model for AmberClaw."""
    role: MessageRole
    content: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    """A sequence of messages forming a conversation."""
    id: str
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
