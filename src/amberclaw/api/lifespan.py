import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from amberclaw.governance.board import GovernanceBoard
from amberclaw.heartbeat.engine import HeartbeatEngine

logger = logging.getLogger(__name__)

# Global instances for the OS services
# In a full enterprise app, these might be injected via dependencies or a service registry
heartbeat_engine = HeartbeatEngine(check_interval_seconds=5)
governance_board = GovernanceBoard()


@asynccontextmanager
async def os_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manages the startup and shutdown lifecycle of the AmberClaw AI OS.
    This ensures background tasks (like the heartbeat) start correctly
    when the API boots and shut down gracefully on exit.
    """
    logger.info("Starting AmberClaw OS Lifespan...")

    app.state.heartbeat_engine = heartbeat_engine
    app.state.governance_board = governance_board
    app.state.os_started = False
    try:
        await heartbeat_engine.start()
        app.state.os_started = True
        logger.info("AmberClaw OS services initialized.")
        yield
    finally:
        app.state.os_started = False
        logger.info("Initiating AmberClaw OS Shutdown...")
        await heartbeat_engine.stop()
        logger.info("AmberClaw OS Shutdown complete.")
