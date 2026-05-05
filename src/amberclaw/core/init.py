"""
AmberClaw OS Initialization Logic
"""
from loguru import logger

from amberclaw.core.events import Event, bus
from amberclaw.tools.toolsets import register_default_tools


async def initialize_os():
    """Perform global OS initialization."""
    logger.info("Initializing AmberClaw AI OS...")
    
    # 1. Register tools
    register_default_tools()
    logger.success("Tools registered successfully.")
    
    # 2. Emit startup event
    await bus.emit(Event(name="os.started", payload={"status": "ready"}))
    
    logger.info("AmberClaw AI OS is ready.")
