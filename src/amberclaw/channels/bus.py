"""
AmberClaw Channel Bus (Manager)
"""

import asyncio
import logging

from amberclaw.channels.base import BaseChannel

logger = logging.getLogger("amberclaw.channels")


class ChannelBus:
    """Manages multiple communication channels."""

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        """Register a channel."""
        self._channels[channel.name] = channel
        logger.info(f"Registered channel: {channel.name}")

    async def start_all(self) -> None:
        """Start all registered channels."""
        tasks = [channel.start() for channel in self._channels.values()]
        if tasks:
            await asyncio.gather(*tasks)

    async def stop_all(self) -> None:
        """Stop all registered channels."""
        tasks = [channel.stop() for channel in self._channels.values()]
        if tasks:
            await asyncio.gather(*tasks)

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self._channels.get(name)


# Global channel bus instance
bus = ChannelBus()
