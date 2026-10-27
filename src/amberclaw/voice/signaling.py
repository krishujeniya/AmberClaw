import json
from typing import Any

from pydantic import BaseModel, Field

from amberclaw.voice.realtime import RealtimeSessionManager


class SignalingMessage(BaseModel):
    """Schema for WebRTC signaling messages."""

    type: str = Field(
        ...,
        description="Message type: 'offer', 'answer', 'candidate', 'audio', 'interrupt', 'close'",
    )
    session_id: str | None = Field(default=None, description="Voice session ID.")
    sdp: str | None = Field(
        default=None, description="SDP string for WebRTC negotiation."
    )
    candidate: dict[str, Any] | None = Field(
        default=None, description="ICE candidate metadata."
    )
    payload: str | None = Field(
        default=None, description="Base64 encoded audio payload or text data."
    )


class WebRTCSignalingHandler:
    """Signaling handler for managing WebRTC session setup and audio message exchange over WebSockets."""

    def __init__(self, session_manager: RealtimeSessionManager | None = None):
        self.manager = session_manager or RealtimeSessionManager()

    async def handle_signaling_json(
        self, raw_json: str, agent_callback: Any = None
    ) -> str:
        """Process incoming JSON signaling message and return JSON response."""
        try:
            data = json.loads(raw_json)
            msg = SignalingMessage(**data)
        except Exception as ex:
            return json.dumps(
                {"type": "error", "error": f"Invalid signaling payload: {ex}"}
            )

        session_id = msg.session_id or "default-session"
        session = self.manager.get_session(session_id)

        if msg.type == "offer":
            if not session:
                session = self.manager.create_session(
                    session_id=session_id, agent_callback=agent_callback
                )
                await session.start()

            # Return simulated SDP answer for WebRTC session negotiation
            return json.dumps(
                {
                    "type": "answer",
                    "session_id": session_id,
                    "sdp": f"v=0\r\no=- {session_id} 2 IN IP4 127.0.0.1\r\ns=AmberClaw Voice\r\nt=0 0\r\n",
                }
            )

        if msg.type == "candidate":
            return json.dumps({"type": "candidate_ack", "session_id": session_id})

        if msg.type == "interrupt":
            if session:
                session.cancel_outbound_tts()
            return json.dumps({"type": "interrupted", "session_id": session_id})

        if msg.type == "close":
            if session:
                await self.manager.close_session(session_id)
            return json.dumps({"type": "closed", "session_id": session_id})

        return json.dumps({"type": "ack", "session_id": session_id})
