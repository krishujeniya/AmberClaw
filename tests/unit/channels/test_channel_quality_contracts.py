"""Offline lifecycle and media contracts for the channel quality repairs."""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.feishu import FeishuChannel, _extract_interactive_content
from amberclaw.channels.mochat import MochatChannel
from amberclaw.channels.slack import SlackChannel
from amberclaw.channels.telegram import TelegramChannel
from amberclaw.config.schema import (
    FeishuConfig,
    MochatConfig,
    SlackConfig,
    TelegramConfig,
)

OFFLINE_AUTH_VALUE = "offline"
RESTART_CYCLES = 2


@pytest.mark.asyncio
@pytest.mark.parametrize("direct_flag", [False, True])
async def test_slack_stop_wakes_start_and_allows_restart(
    monkeypatch: pytest.MonkeyPatch, direct_flag: bool
) -> None:
    """Both the normal shutdown API and legacy callback flag wake the listener."""
    connected = asyncio.Event()
    socket = SimpleNamespace(
        socket_mode_request_listeners=[],
        connect=AsyncMock(side_effect=connected.set),
        close=AsyncMock(),
    )
    web = SimpleNamespace(auth_test=AsyncMock(return_value={"user_id": "bot"}))
    monkeypatch.setattr(
        "amberclaw.channels.slack.SocketModeClient", Mock(return_value=socket)
    )
    monkeypatch.setattr(
        "amberclaw.channels.slack.AsyncWebClient", Mock(return_value=web)
    )
    channel = SlackChannel(
        SlackConfig(bot_token=OFFLINE_AUTH_VALUE, app_token=OFFLINE_AUTH_VALUE),
        MessageBus(),
    )

    for _ in range(RESTART_CYCLES):
        connected.clear()
        task = asyncio.create_task(channel.start())
        await asyncio.wait_for(connected.wait(), timeout=1)
        assert not task.done()
        if direct_flag:
            channel._running = False
        else:
            await channel.stop()
        await asyncio.wait_for(task, timeout=0.1)
        assert not channel.is_running


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["image", "voice", "audio", "file"])
async def test_telegram_media_preserves_caption_and_failure_tag(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """A media failure still publishes caption, topic metadata and sender identity."""
    bus = MessageBus()
    channel = TelegramChannel(
        TelegramConfig(allow_from=["*"], group_policy="open"), bus
    )
    channel._app = SimpleNamespace(
        bot=SimpleNamespace(get_file=AsyncMock(side_effect=OSError("offline")))
    )
    monkeypatch.setattr(channel, "_start_typing", Mock())
    media = SimpleNamespace(file_id="offline-file", mime_type=None, file_name=None)
    user = SimpleNamespace(id=7, username="alice", first_name="Alice")
    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup", is_forum=True),
        chat_id=42,
        message_id=8,
        message_thread_id=9,
        media_group_id=None,
        text="hello",
        caption="caption",
        photo=[media] if kind == "image" else [],
        voice=media if kind == "voice" else None,
        audio=media if kind == "audio" else None,
        document=media if kind == "file" else None,
    )
    await channel._on_message(
        SimpleNamespace(message=message, effective_user=user), None
    )
    inbound = await bus.consume_inbound()
    assert inbound.content == f"hello\ncaption\n[{kind}: download failed]"
    assert inbound.sender_id == "7|alice"
    assert inbound.media == []
    assert inbound.session_key_override == "telegram:42:topic:9"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["image", "audio", "file", "media", "post"])
async def test_feishu_media_routing_preserves_paths_and_text(kind: str) -> None:
    bus = MessageBus()
    channel = FeishuChannel(FeishuConfig(allow_from=["*"]), bus)
    channel._add_reaction = AsyncMock()
    channel._download_and_save_media = AsyncMock(
        return_value=("/offline/media", "[attachment]")
    )
    message = SimpleNamespace(
        message_id="m1",
        chat_id="chat",
        chat_type="group",
        message_type=kind,
        content='{"content":[[{"tag":"img","image_key":"img1"}]]}'
        if kind == "post"
        else "{}",
    )
    event = SimpleNamespace(
        message=message,
        sender=SimpleNamespace(
            sender_type="user", sender_id=SimpleNamespace(open_id="alice")
        ),
    )
    await channel._on_message(SimpleNamespace(event=event))
    inbound = await bus.consume_inbound()
    assert inbound.chat_id == "chat"
    assert inbound.content == "[attachment]"
    assert inbound.media == ["/offline/media"]


def test_feishu_card_extraction_keeps_nested_order() -> None:
    card: dict[str, Any] = {
        "title": {"content": "Heading"},
        "elements": [
            [
                {
                    "tag": "div",
                    "text": {"content": "Body"},
                    "fields": [{"text": {"content": "Field"}}],
                },
                {"tag": "a", "href": "https://example.com", "text": "Link"},
                {
                    "tag": "button",
                    "text": {"content": "Go"},
                    "multi_url": {"url": "https://example.com/go"},
                },
                {
                    "tag": "column_set",
                    "columns": [
                        {"elements": [{"tag": "plain_text", "content": "Column"}]}
                    ],
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "img", "alt": {"content": "Alt"}}],
                },
            ]
        ],
        "card": {"title": "Nested"},
        "header": {"title": {"content": "Header"}},
    }
    assert _extract_interactive_content(card) == [
        "title: Heading",
        "Body",
        "Field",
        "link: https://example.com",
        "Link",
        "Go",
        "link: https://example.com/go",
        "Column",
        "Alt",
        "title: Nested",
        "title: Header",
    ]


@pytest.mark.asyncio
async def test_telegram_stop_wakes_start_and_restarts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()

    def polling_started(**_kwargs: Any) -> None:
        started.set()

    app = SimpleNamespace(
        bot=SimpleNamespace(
            get_me=AsyncMock(return_value=SimpleNamespace(id=1, username="offline")),
            set_my_commands=AsyncMock(),
        ),
        updater=SimpleNamespace(
            start_polling=AsyncMock(side_effect=polling_started), stop=AsyncMock()
        ),
        add_handler=Mock(),
        add_error_handler=Mock(),
        initialize=AsyncMock(),
        start=AsyncMock(),
        stop=AsyncMock(),
        shutdown=AsyncMock(),
    )
    builder = Mock()
    for method in ("token", "request", "get_updates_request"):
        getattr(builder, method).return_value = builder
    builder.build.return_value = app
    monkeypatch.setattr(
        "amberclaw.channels.telegram.Application",
        SimpleNamespace(builder=Mock(return_value=builder)),
    )
    monkeypatch.setattr("amberclaw.channels.telegram.HTTPXRequest", Mock())
    channel = TelegramChannel(TelegramConfig(token=OFFLINE_AUTH_VALUE), MessageBus())
    for _ in range(RESTART_CYCLES):
        started.clear()
        task = asyncio.create_task(channel.start())
        await asyncio.wait_for(started.wait(), timeout=1)
        await channel.stop()
        await asyncio.wait_for(task, timeout=0.1)
        assert not channel.is_running
    assert app.updater.stop.await_count == RESTART_CYCLES
    assert app.shutdown.await_count == RESTART_CYCLES


@pytest.mark.asyncio
async def test_feishu_stop_wakes_start_and_restarts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    builder = Mock()
    for method in (
        "app_id",
        "app_secret",
        "log_level",
        "register_p2_im_message_receive_v1",
        "register_p2_im_message_reaction_created_v1",
        "register_p2_im_message_message_read_v1",
        "register_p2_im_chat_access_event_bot_p2p_chat_entered_v1",
    ):
        getattr(builder, method).return_value = builder
    sdk = SimpleNamespace(
        Client=SimpleNamespace(builder=Mock(return_value=builder)),
        EventDispatcherHandler=SimpleNamespace(builder=Mock(return_value=builder)),
        LogLevel=SimpleNamespace(INFO=1),
        ws=SimpleNamespace(Client=Mock()),
    )
    monkeypatch.setitem(sys.modules, "lark_oapi", sdk)
    monkeypatch.setattr("amberclaw.channels.feishu.FEISHU_AVAILABLE", True)
    monkeypatch.setattr(
        "amberclaw.channels.feishu.threading.Thread",
        Mock(return_value=SimpleNamespace(start=started.set)),
    )
    channel = FeishuChannel(
        FeishuConfig(app_id="offline", app_secret=OFFLINE_AUTH_VALUE), MessageBus()
    )
    for _ in range(RESTART_CYCLES):
        started.clear()
        task = asyncio.create_task(channel.start())
        await asyncio.wait_for(started.wait(), timeout=1)
        await channel.stop()
        await asyncio.wait_for(task, timeout=0.1)
        assert not channel.is_running


@pytest.mark.asyncio
async def test_mochat_stop_wakes_start_and_restarts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started = asyncio.Event()
    channel = MochatChannel(MochatConfig(claw_token=OFFLINE_AUTH_VALUE), MessageBus())
    channel._state_dir = tmp_path
    for method in (
        "_load_session_cursors",
        "_refresh_targets",
        "_save_session_cursors",
        "_stop_fallback_workers",
        "_cancel_delay_timers",
        "_refresh_loop",
    ):
        monkeypatch.setattr(channel, method, AsyncMock())
    monkeypatch.setattr(
        channel,
        "_start_socket_client",
        AsyncMock(side_effect=lambda: started.set() or True),
    )
    monkeypatch.setattr(
        "amberclaw.channels.mochat.httpx.AsyncClient",
        Mock(return_value=SimpleNamespace(aclose=AsyncMock())),
    )
    for _ in range(RESTART_CYCLES):
        started.clear()
        task = asyncio.create_task(channel.start())
        await asyncio.wait_for(started.wait(), timeout=1)
        await channel.stop()
        await asyncio.wait_for(task, timeout=0.1)
        assert not channel.is_running


@pytest.mark.asyncio
async def test_mochat_socket_registration_dispatches_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handlers: dict[str, Callable[..., Awaitable[None]]] = {}

    def event(callback: Callable[..., Awaitable[None]]) -> None:
        handlers[callback.__name__] = callback

    def on(name: str, callback: Callable[..., Awaitable[None]]) -> None:
        handlers[name] = callback

    socket = SimpleNamespace(
        event=event, on=on, connect=AsyncMock(), disconnect=AsyncMock()
    )
    monkeypatch.setattr("amberclaw.channels.mochat.SOCKETIO_AVAILABLE", True)
    monkeypatch.setattr(
        "amberclaw.channels.mochat.socketio",
        SimpleNamespace(AsyncClient=Mock(return_value=socket)),
    )
    channel = MochatChannel(MochatConfig(claw_token=OFFLINE_AUTH_VALUE), MessageBus())
    subscribe = AsyncMock(return_value=True)
    watch = AsyncMock()
    stop_fallback = AsyncMock()
    monkeypatch.setattr(channel, "_subscribe_all", subscribe)
    monkeypatch.setattr(channel, "_handle_watch_payload", watch)
    monkeypatch.setattr(channel, "_stop_fallback_workers", stop_fallback)
    assert await channel._start_socket_client()
    await handlers["connect"]()
    payload = {"sessionId": "session_offline", "events": []}
    await handlers["claw.session.events"](payload)
    subscribe.assert_awaited_once()
    stop_fallback.assert_awaited_once()
    watch.assert_awaited_once_with(payload, "session")
    assert channel._ws_ready


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chat_id,id_key", [("session_offline", "sessionId"), ("panel:offline", "panelId")]
)
async def test_mochat_send_retains_target_and_reply_fields(
    chat_id: str, id_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    channel = MochatChannel(MochatConfig(claw_token=OFFLINE_AUTH_VALUE), MessageBus())
    post = AsyncMock(return_value={})
    monkeypatch.setattr(channel, "_post_json", post)
    await channel.send(
        OutboundMessage(
            channel="mochat",
            chat_id=chat_id,
            content="hello",
            reply_to="previous",
            metadata={"group_id": "group"},
        )
    )
    path, body = post.await_args.args
    assert body[id_key] == ("offline" if id_key == "panelId" else chat_id)
    assert body["replyTo"] == "previous"
    assert body["content"] == "hello"
    if id_key == "panelId":
        assert path == "/api/claw/groups/panels/send"
        assert body["groupId"] == "group"
    else:
        assert path == "/api/claw/sessions/send"
        assert "groupId" not in body
