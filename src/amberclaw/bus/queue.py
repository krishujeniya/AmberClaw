"""Async message queue for decoupled channel-agent communication with Redis Pub/Sub support."""

import asyncio
import json
from datetime import datetime
from typing import Any

from loguru import logger

from amberclaw.bus.events import InboundMessage, OutboundMessage, SystemEvent
from amberclaw.database.redis_client import get_redis


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime serialization."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _serialize(obj: Any) -> str:
    """Helper to serialize objects to JSON string."""
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif hasattr(obj, "dict"):
        data = obj.dict()
    elif hasattr(obj, "__dict__"):
        data = dict(obj.__dict__)
    else:
        data = obj
    return json.dumps(data, cls=CustomJSONEncoder, ensure_ascii=False)


def _deserialize_inbound(data: dict[str, Any]) -> InboundMessage:
    """Helper to deserialize InboundMessage object with datetime fields."""
    if "timestamp" in data and isinstance(data["timestamp"], str):
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
    return InboundMessage(**data)


def _deserialize_outbound(data: dict[str, Any]) -> OutboundMessage:
    """Helper to deserialize OutboundMessage object."""
    return OutboundMessage(**data)


def _deserialize_system_event(data: dict[str, Any]) -> SystemEvent:
    """Helper to deserialize SystemEvent object with datetime fields."""
    if "timestamp" in data and isinstance(data["timestamp"], str):
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
    return SystemEvent(**data)


class MessageBus:
    """Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue. Supports multi-node
    scaling with Redis Pub/Sub.
    """

    def __init__(self) -> None:
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self.system_events: asyncio.Queue[SystemEvent] = asyncio.Queue()
        self._listener_task: asyncio.Task | None = None

    def _ensure_redis_listener(self) -> None:
        """Starts the Redis Pub/Sub subscription loop if Redis is available."""
        if self._listener_task is not None and not self._listener_task.done():
            return

        client = get_redis()
        if client is not None:
            self._listener_task = asyncio.create_task(self._redis_listener_loop(client))
            logger.info("MessageBus Redis Pub/Sub subscription listener started.")

    async def _redis_listener_loop(self, client: Any) -> None:
        """Background loop reading from Redis channels and placing into local queues."""
        pubsub = client.pubsub()
        if asyncio.iscoroutine(pubsub):
            pubsub = await pubsub

        await pubsub.subscribe(
            "amberclaw_inbound",
            "amberclaw_outbound",
            "amberclaw_system_events",
        )
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                channel = message["channel"]
                data = json.loads(message["data"])

                if channel == "amberclaw_inbound":
                    msg = _deserialize_inbound(data)
                    await self.inbound.put(msg)
                elif channel == "amberclaw_outbound":
                    msg = _deserialize_outbound(data)
                    await self.outbound.put(msg)
                elif channel == "amberclaw_system_events":
                    event = _deserialize_system_event(data)
                    await self.system_events.put(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Redis Pub/Sub message bus listener encountered an error: {}", e)
        finally:
            try:
                await pubsub.unsubscribe()
            except Exception:
                pass

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        self._ensure_redis_listener()
        client = get_redis()
        if client:
            try:
                serialized = _serialize(msg)
                pub_res = client.publish("amberclaw_inbound", serialized)
                if asyncio.iscoroutine(pub_res):
                    await pub_res
                return
            except Exception as e:
                logger.warning("Failed to publish inbound event to Redis: {}. Retrying locally.", e)

        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        self._ensure_redis_listener()
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        self._ensure_redis_listener()
        client = get_redis()
        if client:
            try:
                serialized = _serialize(msg)
                pub_res = client.publish("amberclaw_outbound", serialized)
                if asyncio.iscoroutine(pub_res):
                    await pub_res
                return
            except Exception as e:
                logger.warning("Failed to publish outbound event to Redis: {}. Retrying locally.", e)

        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        self._ensure_redis_listener()
        return await self.outbound.get()

    async def publish_system_event(self, event: SystemEvent) -> None:
        """Publish a system event."""
        self._ensure_redis_listener()
        client = get_redis()
        if client:
            try:
                serialized = _serialize(event)
                pub_res = client.publish("amberclaw_system_events", serialized)
                if asyncio.iscoroutine(pub_res):
                    await pub_res
                return
            except Exception as e:
                logger.warning("Failed to publish system event to Redis: {}. Retrying locally.", e)

        await self.system_events.put(event)

    async def consume_system_event(self) -> SystemEvent:
        """Consume the next system event (blocks until available)."""
        self._ensure_redis_listener()
        return await self.system_events.get()

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()

    @property
    def system_events_size(self) -> int:
        """Number of pending system events."""
        return self.system_events.qsize()
