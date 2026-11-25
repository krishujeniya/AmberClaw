# ruff: noqa: ERA001
"""Cross-channel user identity mapping and conversation session continuity.

Enables seamless multi-channel agent interactions:
- Mapping platform accounts (e.g. Telegram ID, Discord handle) to unified canonical user IDs.
- Preserving active conversation sessions across channel handovers (e.g., Telegram -> Web Dashboard -> Slack).
"""

from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class IdentityLink(BaseModel):
    """Mapping between an external channel identity and an internal canonical user ID."""

    canonical_user_id: str
    channel: str
    channel_user_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrossChannelContinuityManager:
    """Manages cross-platform identity linking and conversation continuity."""

    _instance: "CrossChannelContinuityManager | None" = None

    def __init__(self) -> None:
        # {(channel, channel_user_id): canonical_user_id}
        self._identity_map: dict[tuple[str, str], str] = {}
        # {canonical_user_id: [(channel, channel_user_id), ...]}
        self._user_identities: dict[str, set[tuple[str, str]]] = {}
        # {canonical_user_id: active_session_id}
        self._canonical_sessions: dict[str, str] = {}
        # {(channel, channel_user_id): session_id}
        self._channel_sessions: dict[tuple[str, str], str] = {}

    @classmethod
    def get_instance(cls) -> "CrossChannelContinuityManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def link_identity(
        self,
        canonical_user_id: str,
        channel: str,
        channel_user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> IdentityLink:
        """Link an external channel identity to a canonical user account."""
        key = (channel.lower().strip(), str(channel_user_id).strip())
        self._identity_map[key] = canonical_user_id

        if canonical_user_id not in self._user_identities:
            self._user_identities[canonical_user_id] = set()
        self._user_identities[canonical_user_id].add(key)

        logger.info(
            "Linked identity '{}:{}' -> canonical user '{}'",
            channel,
            channel_user_id,
            canonical_user_id,
        )
        return IdentityLink(
            canonical_user_id=canonical_user_id,
            channel=channel,
            channel_user_id=channel_user_id,
            metadata=metadata or {},
        )

    def resolve_canonical_user(self, channel: str, channel_user_id: str) -> str:
        """Resolve external channel user to canonical user ID, defaulting to formatted channel ID."""
        key = (channel.lower().strip(), str(channel_user_id).strip())
        return self._identity_map.get(key, f"{channel}_{channel_user_id}")

    def get_linked_identities(self, canonical_user_id: str) -> list[tuple[str, str]]:
        """Retrieve all external channel identities mapped to a canonical user."""
        return list(self._user_identities.get(canonical_user_id, set()))

    def unlink_identity(self, channel: str, channel_user_id: str) -> bool:
        """Remove a channel identity link."""
        key = (channel.lower().strip(), str(channel_user_id).strip())
        canonical_id = self._identity_map.pop(key, None)
        if canonical_id and canonical_id in self._user_identities:
            self._user_identities[canonical_id].discard(key)
            return True
        return False

    def bind_session(self, canonical_user_id: str, session_id: str) -> None:
        """Bind an active session to a canonical user, propagating to all linked channel identities."""
        self._canonical_sessions[canonical_user_id] = session_id
        for key in self._user_identities.get(canonical_user_id, set()):
            self._channel_sessions[key] = session_id

    def handover_session(
        self,
        from_channel: str,
        from_user_id: str,
        to_channel: str,
        to_user_id: str,
        session_id: str,
    ) -> None:
        """Transfer an active conversation session between two channel identities."""
        from_key = (from_channel.lower().strip(), str(from_user_id).strip())
        to_key = (to_channel.lower().strip(), str(to_user_id).strip())

        self._channel_sessions[from_key] = session_id
        self._channel_sessions[to_key] = session_id

        # Also link canonical user if mapped
        canonical_id = self._identity_map.get(from_key) or self._identity_map.get(
            to_key
        )
        if canonical_id:
            self.bind_session(canonical_id, session_id)

        logger.info(
            "Session handover '{}:{}' -> '{}:{}' for session '{}'",
            from_channel,
            from_user_id,
            to_channel,
            to_user_id,
            session_id,
        )

    def get_active_session(self, channel: str, channel_user_id: str) -> str | None:
        """Get the active session ID for a channel user, checking canonical user session fallback."""
        key = (channel.lower().strip(), str(channel_user_id).strip())
        if key in self._channel_sessions:
            return self._channel_sessions[key]

        canonical_id = self._identity_map.get(key)
        if canonical_id:
            return self._canonical_sessions.get(canonical_id)
        return None

    def clear(self) -> None:
        self._identity_map.clear()
        self._user_identities.clear()
        self._canonical_sessions.clear()
        self._channel_sessions.clear()
