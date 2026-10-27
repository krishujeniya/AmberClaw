# ruff: noqa: ARG001
"""Channel capability matrix, feature declaration, and graceful degradation fallbacks.

Declares rich messaging features supported across messaging platforms:
- Rich formatting (Markdown, HTML)
- Media types (Images, Audio, Video, Files, Voice Notes)
- Conversational features (Threading, Message Edits, Reactions, Typing Indicators)
- Operational bounds (Max message length, Rate limits, Max file size)
"""

from pydantic import BaseModel, Field


class ChannelCapability(BaseModel):
    """Specification of capabilities and limits supported by a channel adapter."""

    channel: str
    text: bool = True
    markdown: bool = True
    html: bool = False
    images: bool = True
    audio: bool = True
    video: bool = False
    files: bool = True
    voice_notes: bool = False
    threading: bool = False
    message_edits: bool = False
    reactions: bool = False
    typing_indicator: bool = True
    max_message_length: int = 4096
    rate_limit_messages_per_sec: float = 1.0
    supported_mime_types: list[str] = Field(
        default_factory=lambda: [
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
            "text/plain",
        ]
    )
    max_file_size_mb: int = 20

    def supports(self, feature_name: str) -> bool:
        """Check whether a specific capability is supported."""
        val = getattr(self, feature_name, None)
        return bool(val)


# Canonical registry of channel capabilities
CHANNEL_CAPABILITIES_CATALOG: dict[str, ChannelCapability] = {
    "telegram": ChannelCapability(
        channel="telegram",
        markdown=True,
        html=True,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=True,
        threading=True,
        message_edits=True,
        reactions=True,
        typing_indicator=True,
        max_message_length=4096,
        rate_limit_messages_per_sec=30.0,
        max_file_size_mb=50,
    ),
    "discord": ChannelCapability(
        channel="discord",
        markdown=True,
        html=False,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=False,
        threading=True,
        message_edits=True,
        reactions=True,
        typing_indicator=True,
        max_message_length=2000,
        rate_limit_messages_per_sec=5.0,
        max_file_size_mb=25,
    ),
    "slack": ChannelCapability(
        channel="slack",
        markdown=True,
        html=False,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=True,
        threading=True,
        message_edits=True,
        reactions=True,
        typing_indicator=True,
        max_message_length=4000,
        rate_limit_messages_per_sec=1.0,
        max_file_size_mb=100,
    ),
    "matrix": ChannelCapability(
        channel="matrix",
        markdown=True,
        html=True,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=True,
        threading=True,
        message_edits=True,
        reactions=True,
        typing_indicator=True,
        max_message_length=65535,
        rate_limit_messages_per_sec=10.0,
        max_file_size_mb=100,
    ),
    "email": ChannelCapability(
        channel="email",
        markdown=True,
        html=True,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=False,
        threading=True,
        message_edits=False,
        reactions=False,
        typing_indicator=False,
        max_message_length=1000000,
        rate_limit_messages_per_sec=0.2,
        max_file_size_mb=25,
    ),
    "whatsapp": ChannelCapability(
        channel="whatsapp",
        markdown=True,
        html=False,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=True,
        threading=False,
        message_edits=False,
        reactions=True,
        typing_indicator=True,
        max_message_length=4096,
        rate_limit_messages_per_sec=10.0,
        max_file_size_mb=16,
    ),
    "feishu": ChannelCapability(
        channel="feishu",
        markdown=True,
        html=False,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=True,
        threading=True,
        message_edits=True,
        reactions=True,
        typing_indicator=True,
        max_message_length=10000,
        rate_limit_messages_per_sec=5.0,
        max_file_size_mb=30,
    ),
    "dingtalk": ChannelCapability(
        channel="dingtalk",
        markdown=True,
        html=False,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=True,
        threading=False,
        message_edits=False,
        reactions=False,
        typing_indicator=False,
        max_message_length=5000,
        rate_limit_messages_per_sec=20.0,
        max_file_size_mb=20,
    ),
    "mochat": ChannelCapability(
        channel="mochat",
        markdown=True,
        html=False,
        images=True,
        audio=True,
        video=True,
        files=True,
        voice_notes=False,
        threading=False,
        message_edits=False,
        reactions=False,
        typing_indicator=False,
        max_message_length=2048,
        rate_limit_messages_per_sec=2.0,
        max_file_size_mb=10,
    ),
    "qq": ChannelCapability(
        channel="qq",
        markdown=False,
        html=False,
        images=True,
        audio=True,
        video=False,
        files=True,
        voice_notes=False,
        threading=False,
        message_edits=False,
        reactions=False,
        typing_indicator=False,
        max_message_length=1000,
        rate_limit_messages_per_sec=1.0,
        max_file_size_mb=10,
    ),
    "cli": ChannelCapability(
        channel="cli",
        markdown=True,
        html=False,
        images=False,
        audio=False,
        video=False,
        files=False,
        voice_notes=False,
        threading=False,
        message_edits=True,
        reactions=False,
        typing_indicator=True,
        max_message_length=100000,
        rate_limit_messages_per_sec=100.0,
        max_file_size_mb=0,
    ),
}


def get_channel_capability(channel_name: str) -> ChannelCapability:
    """Retrieve capability profile for a channel, returning safe defaults if unknown."""
    normalized = channel_name.lower().strip()
    return CHANNEL_CAPABILITIES_CATALOG.get(
        normalized,
        ChannelCapability(channel=normalized),
    )


def register_channel_capability(capability: ChannelCapability) -> None:
    """Register or override a channel capability profile."""
    CHANNEL_CAPABILITIES_CATALOG[capability.channel.lower().strip()] = capability


def check_channel_support(channel_name: str, feature: str) -> bool:
    """Check if a channel supports a specific messaging feature."""
    cap = get_channel_capability(channel_name)
    return cap.supports(feature)


def explain_unsupported_action(channel_name: str, feature: str) -> str:
    """Return a human-readable explanation when a channel lacks a feature."""
    cap = get_channel_capability(channel_name)
    feature_clean = feature.replace("_", " ")

    explanations = {
        "reactions": f"Platform '{channel_name}' does not support emoji reactions.",
        "threading": f"Channel '{channel_name}' does not support threaded message replies; message delivered to main conversation.",
        "voice_notes": f"Channel '{channel_name}' does not support native voice notes; sending as audio file.",
        "html": f"Channel '{channel_name}' does not support HTML formatting; converted to standard Markdown/plain text.",
        "markdown": f"Channel '{channel_name}' does not support Markdown formatting; stripped to plain text.",
        "message_edits": f"Channel '{channel_name}' does not support modifying sent messages.",
    }
    return explanations.get(
        feature,
        f"Feature '{feature_clean}' is not supported on '{channel_name}' (max message length: {cap.max_message_length} chars).",
    )


def format_graceful_fallback(
    channel_name: str, feature: str, fallback_content: str
) -> str:
    """Format fallback content when a platform feature cannot be used directly."""
    if feature == "reactions":
        return f"[Reaction: {fallback_content}]"
    if feature == "voice_notes":
        return f"🎙️ [Voice Note Transcript]: {fallback_content}"
    if feature == "threading":
        return f"[Thread Reply]: {fallback_content}"
    return fallback_content
