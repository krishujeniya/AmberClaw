import logging
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
async def os_lifespan(app: FastAPI):
    """
    Manages the startup and shutdown lifecycle of the AmberClaw AI OS.
    This ensures background tasks (like the heartbeat) start correctly
    when the API boots and shut down gracefully on exit.
    """
    logger.info("Starting AmberClaw OS Lifespan...")
    
    # 1. Start the Heartbeat Engine
    await heartbeat_engine.start()
    
    # 2. Add other core OS initializations here (Memory, DB connections, etc.)
    logger.info("AmberClaw OS fully initialized and ready.")

    # Yield control back to FastAPI so it can start serving requests
    yield
    
    logger.info("Initiating AmberClaw OS Shutdown...")
    
    # 1. Stop the Heartbeat Engine gracefully
    await heartbeat_engine.stop()
    
    # 2. Add other cleanup here
    logger.info("AmberClaw OS Shutdown complete.")
