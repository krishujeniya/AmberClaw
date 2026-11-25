"""Channel manager for coordinating chat channels."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from loguru import logger

from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel
from amberclaw.config.schema import Config


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Config, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task[Any] | None = None

        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize channels based on config."""

        self._init_telegram()
        self._init_whatsapp()
        self._init_discord()
        self._init_feishu()
        self._init_mochat()
        self._init_dingtalk()
        self._init_email()
        self._init_slack()
        self._init_qq()
        self._init_matrix()
        self._validate_allow_from()

    def _init_telegram(self) -> None:
        # Telegram channel
        if self.config.channels.telegram.enabled:
            try:
                from amberclaw.channels.telegram import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    TelegramChannel,
                )

                self.channels["telegram"] = TelegramChannel(
                    self.config.channels.telegram,
                    self.bus,
                    groq_api_key=self.config.providers.groq.api_key,
                )
                logger.info("Telegram channel enabled")
            except ImportError as e:
                logger.warning("Telegram channel not available: {}", e)

    def _init_whatsapp(self) -> None:
        # WhatsApp channel
        if self.config.channels.whatsapp.enabled:
            try:
                from amberclaw.channels.whatsapp import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    WhatsAppChannel,
                )

                self.channels["whatsapp"] = WhatsAppChannel(
                    self.config.channels.whatsapp, self.bus
                )
                logger.info("WhatsApp channel enabled")
            except ImportError as e:
                logger.warning("WhatsApp channel not available: {}", e)

    def _init_discord(self) -> None:
        # Discord channel
        if self.config.channels.discord.enabled:
            try:
                from amberclaw.channels.discord import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    DiscordChannel,
                )

                self.channels["discord"] = DiscordChannel(
                    self.config.channels.discord, self.bus
                )
                logger.info("Discord channel enabled")
            except ImportError as e:
                logger.warning("Discord channel not available: {}", e)

    def _init_feishu(self) -> None:
        # Feishu channel
        if self.config.channels.feishu.enabled:
            try:
                from amberclaw.channels.feishu import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    FeishuChannel,
                )

                self.channels["feishu"] = FeishuChannel(
                    self.config.channels.feishu,
                    self.bus,
                    groq_api_key=self.config.providers.groq.api_key,
                )
                logger.info("Feishu channel enabled")
            except ImportError as e:
                logger.warning("Feishu channel not available: {}", e)

    def _init_mochat(self) -> None:
        # Mochat channel
        if self.config.channels.mochat.enabled:
            try:
                from amberclaw.channels.mochat import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    MochatChannel,
                )

                self.channels["mochat"] = MochatChannel(
                    self.config.channels.mochat, self.bus
                )
                logger.info("Mochat channel enabled")
            except ImportError as e:
                logger.warning("Mochat channel not available: {}", e)

    def _init_dingtalk(self) -> None:
        # DingTalk channel
        if self.config.channels.dingtalk.enabled:
            try:
                from amberclaw.channels.dingtalk import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    DingTalkChannel,
                )

                self.channels["dingtalk"] = DingTalkChannel(
                    self.config.channels.dingtalk, self.bus
                )
                logger.info("DingTalk channel enabled")
            except ImportError as e:
                logger.warning("DingTalk channel not available: {}", e)

    def _init_email(self) -> None:
        # Email channel
        if self.config.channels.email.enabled:
            try:
                from amberclaw.channels.email import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    EmailChannel,
                )

                self.channels["email"] = EmailChannel(
                    self.config.channels.email, self.bus
                )
                logger.info("Email channel enabled")
            except ImportError as e:
                logger.warning("Email channel not available: {}", e)

    def _init_slack(self) -> None:
        # Slack channel
        if self.config.channels.slack.enabled:
            try:
                from amberclaw.channels.slack import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    SlackChannel,
                )

                self.channels["slack"] = SlackChannel(
                    self.config.channels.slack, self.bus
                )
                logger.info("Slack channel enabled")
            except ImportError as e:
                logger.warning("Slack channel not available: {}", e)

    def _init_qq(self) -> None:
        # QQ channel
        if self.config.channels.qq.enabled:
            try:
                from amberclaw.channels.qq import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    QQChannel,
                )

                self.channels["qq"] = QQChannel(
                    self.config.channels.qq,
                    self.bus,
                )
                logger.info("QQ channel enabled")
            except ImportError as e:
                logger.warning("QQ channel not available: {}", e)

    def _init_matrix(self) -> None:
        # Matrix channel
        if self.config.channels.matrix.enabled:
            try:
                from amberclaw.channels.matrix import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    MatrixChannel,
                )

                self.channels["matrix"] = MatrixChannel(
                    self.config.channels.matrix,
                    self.bus,
                )
                logger.info("Matrix channel enabled")
            except ImportError as e:
                logger.warning("Matrix channel not available: {}", e)

    def _validate_allow_from(self) -> None:
        for name, ch in self.channels.items():
            if getattr(ch.config, "allow_from", None) == []:
                raise SystemExit(
                    f'Error: "{name}" has empty allowFrom (denies all). '
                    f'Set ["*"] to allow everyone, or add specific user IDs.',
                )

    async def _start_channel(self, name: str, channel: BaseChannel) -> None:
        """Start a channel and log any exceptions."""
        try:
            await channel.start()
        except Exception as e:
            logger.error("Failed to start channel {}: {}", name, e)

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            return

        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # Start channels
        tasks = []
        for name, channel in self.channels.items():
            logger.info("Starting {} channel...", name)
            tasks.append(asyncio.create_task(self._start_channel(name, channel)))

        # Wait for all to complete (they should run forever)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")

        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._dispatch_task

        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info("Stopped {} channel", name)
            except Exception as e:
                logger.error("Error stopping {}: {}", name, e)

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(self.bus.consume_outbound(), timeout=1.0)

                if msg.metadata.get("_progress"):
                    if (
                        msg.metadata.get("_tool_hint")
                        and not self.config.channels.send_tool_hints
                    ):
                        continue
                    if (
                        not msg.metadata.get("_tool_hint")
                        and not self.config.channels.send_progress
                    ):
                        continue

                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error("Error sending to {}: {}", msg.channel, e)
                else:
                    logger.warning("Unknown channel: {}", msg.channel)

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {"enabled": True, "running": channel.is_running}
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())
