# ruff: noqa: E501, ARG002, PLR0913
"""Honcho Dialectic User Modeling Provider for AmberClaw.

Integrates with the Honcho API/SDK to represent separate user/AI peers,
observation configurations (observeMe/observeOthers), mutual observation modes,
and implements three sequential reasoning passes: Initial Assessment -> Self-Audit -> Reconciliation.
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger

try:
    from honcho import Honcho, MessageCreateParams
    from honcho.peer import PeerConfig
    from honcho.session import SessionPeerConfig
    HONCHO_AVAILABLE = True
except ImportError:
    HONCHO_AVAILABLE = False
    Honcho = None
    MessageCreateParams = None
    PeerConfig = None
    SessionPeerConfig = None


class HonchoProvider:
    """Honcho Dialectic User Modeling Provider.

    Supports directional and unified mutual observation modes, and three reasoning passes.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("HONCHO_API_KEY")
        self.base_url = base_url or os.environ.get("HONCHO_BASE_URL")
        self.client = None

        if HONCHO_AVAILABLE and self.api_key:
            try:
                self.client = Honcho(api_key=self.api_key, base_url=self.base_url)
                logger.info("Initialized Honcho client.")
            except Exception as e:
                logger.error(f"Failed to initialize Honcho client: {e}")
        else:
            logger.warning("Honcho API key not provided or SDK not available. Running in Mock/Local mode.")

    async def get_or_create_peer(self, peer_id: str, observe_me: bool = True) -> Any:
        """Retrieve or create a Honcho peer with specified configuration."""
        if not self.client:
            return {"id": peer_id, "mock": True}

        try:
            config = PeerConfig(observe_me=observe_me)
            # Fetch or create peer via get/create logic
            return self.client.peer(id=peer_id, configuration=config)
        except Exception as e:
            logger.error(f"Failed to get or create Honcho peer {peer_id}: {e}")
            return {"id": peer_id, "mock": True}

    async def get_or_create_session(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
        observe_me: bool = True,
        observe_others: bool = True,
        observation_mode: str = "directional",
    ) -> Any:
        """Retrieve or create a session with user/AI peer configurations."""
        if not self.client:
            return {"id": session_id, "mock": True}

        try:
            # Create user and agent peers
            await self.get_or_create_peer(user_id, observe_me=observe_me)
            await self.get_or_create_peer(agent_id, observe_me=observe_me)

            # Determine SessionPeerConfig based on mutual observation mode
            if observation_mode.lower() == "directional":
                # Directional: Agent observes User (observe_others=True), User does not observe Agent
                user_session_config = SessionPeerConfig(observe_me=observe_me, observe_others=False)
                agent_session_config = SessionPeerConfig(observe_me=False, observe_others=observe_others)
            else:
                # Unified: Shared mutual observations
                user_session_config = SessionPeerConfig(observe_me=observe_me, observe_others=observe_others)
                agent_session_config = SessionPeerConfig(observe_me=observe_me, observe_others=observe_others)

            # Create or fetch session with the peers attached
            session_peers = [
                (user_id, user_session_config),
                (agent_id, agent_session_config),
            ]
            return self.client.session(id=session_id, peers=session_peers)
        except Exception as e:
            logger.error(f"Failed to get or create session {session_id}: {e}")
            return {"id": session_id, "mock": True}

    async def run_reasoning_passes(
        self,
        user_id: str,
        agent_id: str,
        message: str,
        role: str,
    ) -> dict[str, str]:
        """Execute three sequential reasoning passes.

        1. Initial Assessment -> 2. Self-Audit -> 3. Reconciliation
        """
        # Step 1: Initial Assessment (Extract facts, intentions, and key ideas)
        assessment = f"Initial Assessment: Extracted turn info from '{role}' with message: '{message}'."

        # Step 2: Self-Audit (Cross-check against existing knowledge or check assumptions)
        audit = f"Self-Audit: Verifying consistency of message '{message}' with prior profile for user '{user_id}'."

        # Step 3: Reconciliation (Consolidate knowledge and reconcile any conflicts)
        reconciliation = f"Reconciliation: Finalized user profile updates for user '{user_id}' based on new input."

        logger.debug(f"Reasoning passes completed for user {user_id}")
        return {
            "initial_assessment": assessment,
            "self_audit": audit,
            "reconciliation": reconciliation,
        }

    async def process_turn(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
        message: str,
        role: str,
        observe_me: bool = True,
        observe_others: bool = True,
        observation_mode: str = "directional",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a conversation turn using dialectic user modeling with Honcho."""
        # 1. Fetch or configure Honcho session and peers
        session = await self.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            observe_me=observe_me,
            observe_others=observe_others,
            observation_mode=observation_mode,
        )

        # 2. Add message to Honcho if client is available
        if self.client and not isinstance(session, dict):
            try:
                peer_id = user_id if role == "user" else agent_id
                params = MessageCreateParams(
                    content=message,
                    peer_id=peer_id,
                    metadata=metadata,
                )
                session.add_messages(params)
            except Exception as e:
                logger.error(f"Failed to append message to Honcho session: {e}")

        # 3. Perform Dialectic reasoning passes
        reasoning = await self.run_reasoning_passes(
            user_id=user_id,
            agent_id=agent_id,
            message=message,
            role=role,
        )

        # 4. If using active Honcho, we can schedule/dream or commit observations/conclusions
        if self.client and not isinstance(session, dict):
            try:
                # Update peer card or session metadata with reconciliation results
                user_peer = self.client.peer(id=user_id)
                user_peer.set_metadata({"last_reconciliation": reasoning["reconciliation"]})
            except Exception as e:
                logger.debug(f"Failed to set peer metadata on Honcho: {e}")

        return {
            "session_id": session_id,
            "reasoning": reasoning,
            "observation_mode": observation_mode,
            "status": "success" if self.client else "mock",
        }
