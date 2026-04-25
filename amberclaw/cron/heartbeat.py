"""Heartbeat service for signaling agent health and periodic tasks."""

import asyncio
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from amberclaw.providers.base import LLMProvider


class HeartbeatService:
    """Service that periodically updates a heartbeat file and executes optional tasks."""

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        on_execute: Callable[[str], Awaitable[str]],
        on_notify: Callable[[str], Awaitable[None]],
        interval_s: int = 3600,
        enabled: bool = True,
    ):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_s = interval_s
        self.enabled = enabled

        self.heartbeat_file = workspace / "heartbeat.txt"
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the heartbeat background task."""
        if not self.enabled or self._running:
            return
        self._running = True
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._task = asyncio.create_task(self._run())
        logger.info("Heartbeat service started (interval: {}s)", self.interval_s)

    async def _run(self) -> None:
        """Background loop for updating the heartbeat file and executing tasks."""
        while self._running:
            try:
                # 1. Update heartbeat file
                self.heartbeat_file.write_text(str(int(time.time())), encoding="utf-8")

                # 2. Execute heartbeat task (check-in)
                # In the future, this could pull from a dedicated heartbeat.md prompt
                prompt = "Perform a brief internal check-in. Report status."
                response = await self.on_execute(prompt)
                if response:
                    await self.on_notify(response)

            except Exception as e:
                logger.error("Heartbeat loop error: {}", e)

            try:
                await asyncio.sleep(self.interval_s)
            except asyncio.CancelledError:
                break

    async def stop(self) -> None:
        """Stop the heartbeat background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat service stopped")
