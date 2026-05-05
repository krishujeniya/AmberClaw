"""
AmberClaw OS Orchestrator
"""
import asyncio

from loguru import logger

from amberclaw.agent.core import BaseAgent
from amberclaw.agent.loop import AgentLoop
from amberclaw.channels import BaseChannel, DiscordChannel, TelegramChannel
from amberclaw.config.schema import settings
from amberclaw.models.message import Message


class Orchestrator:
    """Main OS orchestrator managing channels and agents."""
    
    def __init__(self):
        self.channels: dict[str, BaseChannel] = {}
        self.agents: dict[str, BaseAgent] = {}
        self._running_tasks: list[asyncio.Task] = []

    async def start(self):
        """Start all configured components."""
        logger.info("Starting AmberClaw Orchestrator...")
        
        # 1. Start Channels
        if settings.telegram.enabled:
            tg = TelegramChannel(settings.telegram)
            tg.set_message_handler(self.handle_inbound_message)
            self.channels["telegram"] = tg
            await tg.start()
            
        if settings.discord.enabled:
            ds = DiscordChannel(settings.discord)
            ds.set_message_handler(self.handle_inbound_message)
            self.channels["discord"] = ds
            await ds.start()

        logger.info("Orchestrator started successfully")

    async def stop(self):
        """Stop all components."""
        logger.info("Stopping AmberClaw Orchestrator...")
        for channel in self.channels.values():
            await channel.stop()
        
        for task in self._running_tasks:
            task.cancel()
            
        logger.info("Orchestrator stopped")

    async def handle_inbound_message(self, message: Message):
        """Route inbound message to the appropriate agent."""
        # For now, we use a single default agent or create one per session
        # In a real system, we'd lookup or create an agent for this user/chat
        
        agent_id = f"user_{message.metadata.get('user_id', 'unknown')}"
        if agent_id not in self.agents:
            from amberclaw.agent.core import BaseAgent
            self.agents[agent_id] = BaseAgent(id=agent_id, name="User Assistant")
            
        agent = self.agents[agent_id]
        loop = AgentLoop(agent)
        
        # Process in background to avoid blocking the channel listener
        task = asyncio.create_task(self._process_message(loop, message))
        self._running_tasks.append(task)
        task.add_done_callback(lambda t: self._running_tasks.remove(t) if t in self._running_tasks else None)

    async def _process_message(self, loop: AgentLoop, message: Message):
        """Execute agent loop and send responses back."""
        try:
            # We pass the message in a list as expected by AgentLoop.run
            async for response in loop.run([message]):
                # Send response back to the originating channel
                channel_name = message.metadata.get("channel_name", "telegram") # Default if not specified
                if channel_name in self.channels:
                    channel = self.channels[channel_name]
                    
                    # Determine recipient
                    recipient_id = None
                    if channel_name == "telegram":
                        recipient_id = message.metadata.get("chat_id")
                    elif channel_name == "discord":
                        recipient_id = message.metadata.get("channel_id")
                        
                    if recipient_id:
                        await channel.send(response, recipient_id)
        except Exception as e:
            logger.exception(f"Error processing message: {e}")

# Global orchestrator instance
orchestrator = Orchestrator()
