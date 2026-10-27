import pytest

from amberclaw.multimodal.screenshare import (
    ScreenAnalysisResult,
    ScreenShareSession,
)


@pytest.mark.asyncio
async def test_screenshare_session_lifecycle():
    session = ScreenShareSession(session_id="test-screen-1")
    await session.start()
    assert session.is_active is True

    # Push screen frame
    dummy_frame = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xd9"
    )
    session.push_frame(dummy_frame)

    result = await session.analyze_latest_frame()
    assert isinstance(result, ScreenAnalysisResult)
    assert result.active_context == "Code Editor / Terminal"
    assert len(result.suggested_actions) > 0

    await session.stop()
    assert session.is_active is False


@pytest.mark.asyncio
async def test_screenshare_vision_callback():
    session = ScreenShareSession(session_id="test-screen-2")
    await session.start()

    session.push_frame(b"\x89PNG\r\n\x1a\n")

    async def mock_vision(vision_item: dict) -> str:
        return "Detected Python syntax error on line 42."

    result = await session.analyze_latest_frame(vision_callback=mock_vision)
    assert "Python syntax error" in result.guidance_notes

    await session.stop()
