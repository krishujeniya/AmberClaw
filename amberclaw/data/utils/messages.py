from __future__ import annotations

from typing import Sequence

from langchain_core.messages import BaseMessage


def get_tool_call_names(messages: Sequence[BaseMessage]) -> list[str]:
    """
    Method to extract the tool call names from a list of LangChain messages.

    Parameters:
    ----------
    messages : Sequence[BaseMessage]
        A list of LangChain messages.

    Returns:
    -------
    tool_calls : list[str]
        A list of tool call names.

    """
    tool_calls: list[str] = []
    for message in messages:
        # Check if it's a ToolMessage or has tool_call_id in its dict representation
        try:
            msg_dict = dict(message)
            if "tool_call_id" in msg_dict:
                name = getattr(message, "name", None)
                if name:
                    tool_calls.append(name)
        except (AttributeError, TypeError, ValueError):
            pass
    return tool_calls


def get_last_user_message_content(messages: Sequence[BaseMessage]) -> str:
    """
    Returns the content of the most recent human/user message in a list.
    Falls back to an empty string when missing.
    """
    for msg in reversed(messages or []):
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        if role in ("human", "user"):
            return (getattr(msg, "content", "") or "").strip()
    return ""
