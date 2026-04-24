"""Message tool for sending messages to users."""

from typing import Any, Awaitable, Callable, Optional, Literal
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool
from amberclaw.bus.events import OutboundMessage


class MessageArgs(BaseModel):
    """Arguments for the message tool."""
    content: str = Field(..., description="The message content to send")
    channel: Optional[str] = Field(None, description="Optional: target channel (telegram, discord, etc.)")
    chat_id: Optional[str] = Field(None, description="Optional: target chat/user ID")
    media: Optional[list[str]] = Field(None, description="Optional: list of file paths to attach")
    importance: Literal["low", "medium", "high"] = Field("medium", description="Optional: message importance level")


class MessageTool(PydanticTool):
    """Tool to send messages to users on chat channels."""

    name = "message"
    description = "Send a message to the user. Use this when you want to communicate something."
    args_schema = MessageArgs

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = "",
        default_message_id: str | None = None,
    ):
        super().__init__()
        self._send_callback = send_callback
        self._default_channel = default_channel
        self._default_chat_id = default_chat_id
        self._default_message_id = default_message_id
        self._sent_in_turn: bool = False

    def set_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Set the current message context."""
        self._default_channel = channel
        self._default_chat_id = chat_id
        self._default_message_id = message_id

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback

    def start_turn(self) -> None:
        """Reset per-turn send tracking."""
        self._sent_in_turn = False

    async def run(self, args: MessageArgs) -> str:
        channel = args.channel or self._default_channel
        chat_id = args.chat_id or self._default_chat_id
        message_id = self._default_message_id

        if not channel or not chat_id:
            return "Error: No target channel/chat specified"

        if not self._send_callback:
            return "Error: Message sending not configured"

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=args.content,
            media=args.media or [],
            metadata={
                "message_id": message_id,
                "importance": args.importance,
            },
        )

        try:
            await self._send_callback(msg)
            if channel == self._default_channel and chat_id == self._default_chat_id:
                self._sent_in_turn = True
            media_info = f" with {len(args.media)} attachments" if args.media else ""
            return f"Message sent to {channel}:{chat_id}{media_info}"
        except Exception as e:
            return f"Error sending message: {str(e)}"
