"""The API lifecycle must release background services after request failure."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from amberclaw.api import lifespan


@pytest.mark.asyncio
async def test_lifespan_stops_heartbeat_when_body_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heartbeat = AsyncMock()
    monkeypatch.setattr(lifespan, "heartbeat_engine", heartbeat)
    app = FastAPI()
    with pytest.raises(RuntimeError, match="controlled request failure"):
        async with lifespan.os_lifespan(app):
            raise RuntimeError("controlled request failure")
    heartbeat.start.assert_awaited_once()
    heartbeat.stop.assert_awaited_once()
