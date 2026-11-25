"""Chat channels module with plugin architecture, capability matrix, and resilience."""

from amberclaw.channels.base import BaseChannel
from amberclaw.channels.capabilities import (
    ChannelCapability,
    check_channel_support,
    explain_unsupported_action,
    format_graceful_fallback,
    get_channel_capability,
    register_channel_capability,
)
from amberclaw.channels.continuity import (
    CrossChannelContinuityManager,
    IdentityLink,
)
from amberclaw.channels.manager import ChannelManager
from amberclaw.channels.resilience import (
    ChannelMetricsTracker,
    ChannelRateLimiter,
    ChannelReconnectManager,
    ConnectionState,
)

__all__ = [
    "BaseChannel",
    "ChannelCapability",
    "ChannelManager",
    "ChannelMetricsTracker",
    "ChannelRateLimiter",
    "ChannelReconnectManager",
    "ConnectionState",
    "CrossChannelContinuityManager",
    "IdentityLink",
    "check_channel_support",
    "explain_unsupported_action",
    "format_graceful_fallback",
    "get_channel_capability",
    "register_channel_capability",
]
