import json

import pytest

from amberclaw.voice.realtime import RealtimeSessionManager, RealtimeVoiceSession
from amberclaw.voice.signaling import WebRTCSignalingHandler


@pytest.mark.asyncio
async def test_realtime_session_lifecycle():
    session = RealtimeVoiceSession(session_id="test-session-1")
    await session.start()
    assert session.state.is_active is True

    # Push simulated audio chunks
    pcm_chunk = b"\x00\x00" * 320
    session.push_audio_chunk(pcm_chunk)

    await session.stop()
    assert session.state.is_active is False


@pytest.mark.asyncio
async def test_barge_in_interruption():
    session = RealtimeVoiceSession(session_id="test-bargein")
    await session.start()

    # Simulate agent speaking state
    session.state.is_agent_speaking = True

    # High amplitude speech PCM chunk to trigger VAD
    import math
    import struct

    speech_pcm = bytearray()
    for i in range(320):
        val = int(20000 * math.sin(2 * math.pi * 440 * i / 16000))
        speech_pcm.extend(struct.pack("<h", val))

    session.push_audio_chunk(bytes(speech_pcm))

    # Interruption should have reset agent speaking state and incremented interrupted_count
    assert session.state.is_agent_speaking is False
    assert session.state.interrupted_count == 1

    await session.stop()


@pytest.mark.asyncio
async def test_session_manager():
    manager = RealtimeSessionManager()
    session = manager.create_session("sess-100")
    assert session.session_id == "sess-100"
    assert manager.get_session("sess-100") is session

    await manager.close_session("sess-100")
    assert manager.get_session("sess-100") is None


@pytest.mark.asyncio
async def test_webrtc_signaling_handler():
    handler = WebRTCSignalingHandler()

    offer_payload = json.dumps(
        {
            "type": "offer",
            "session_id": "sig-session-1",
            "sdp": "v=0\r\no=- 12345 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
        }
    )

    response_json = await handler.handle_signaling_json(offer_payload)
    resp_dict = json.loads(response_json)

    assert resp_dict["type"] == "answer"
    assert resp_dict["session_id"] == "sig-session-1"

    # Close session
    close_payload = json.dumps({"type": "close", "session_id": "sig-session-1"})
    close_resp = await handler.handle_signaling_json(close_payload)
    assert json.loads(close_resp)["type"] == "closed"
