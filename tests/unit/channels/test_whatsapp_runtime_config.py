"""Bridge startup must use the channel's credentials and isolated defaults."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from amberclaw.bus.queue import MessageBus
from amberclaw.channels.whatsapp import WhatsAppChannel
from amberclaw.config.schema import WhatsAppConfig


def test_default_bridge_tokens_are_not_shared() -> None:
    first = WhatsAppConfig()
    second = WhatsAppConfig()
    assert first.bridge_token
    assert first.bridge_token != second.bridge_token


@pytest.mark.asyncio
async def test_spawn_uses_the_channel_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = WhatsAppConfig(allow_from=["tester"])
    channel = WhatsAppChannel(config, MessageBus())
    stdout = asyncio.StreamReader()
    stdout.feed_eof()
    stderr = asyncio.StreamReader()
    stderr.feed_eof()
    process = MagicMock(stdout=stdout, stderr=stderr, wait=AsyncMock(return_value=0))
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(
        "amberclaw.security.whatsapp_sandbox.spawn_isolated_whatsapp_bridge", spawn
    )

    class Connection:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def __aenter__(self) -> "Connection":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def send(self, message: str) -> None:
            self.sent.append(message)

        def __aiter__(self) -> "Connection":
            return self

        async def __anext__(self) -> str:
            channel._running = False
            raise StopAsyncIteration

        async def close(self) -> None:
            return None

    connection = Connection()
    monkeypatch.setattr("websockets.connect", lambda _url: connection)
    await channel.start()
    try:
        assert spawn.await_count == 1
        assert spawn.await_args is not None
        assert id(spawn.await_args.args[0]) == id(config)
        assert json.loads(connection.sent[0]) == {
            "type": "auth",
            "token": config.bridge_token,
        }
    finally:
        await channel.stop()
