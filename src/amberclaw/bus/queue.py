"""Async message queue for decoupled channel-agent communication with Redis Pub/Sub support."""

import asyncio
import contextlib
import json
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from amberclaw.bus.events import InboundMessage, OutboundMessage, SystemEvent
from amberclaw.core.metrics import record_dlq_message, record_queue_depth
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
    scaling with Redis Pub/Sub, bounded capacity, and Dead Letter Queue (DLQ).
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self.maxsize = maxsize
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=maxsize)
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=maxsize)
        self.system_events: asyncio.Queue[SystemEvent] = asyncio.Queue(maxsize=maxsize)
        self.dead_letter_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=maxsize
        )
        self._listener_task: asyncio.Task | None = None

    def _push_to_dlq(self, item: Any, reason: str) -> None:
        """Route overflow or failed message to the Dead Letter Queue."""
        dlq_entry = {
            "item": item,
            "reason": reason,
            "enqueued_at": datetime.now(UTC).isoformat(),
        }
        try:
            self.dead_letter_queue.put_nowait(dlq_entry)
            record_dlq_message(reason)
            record_queue_depth("dead_letter_queue", self.dead_letter_queue.qsize())
            logger.warning(
                "Message routed to Dead Letter Queue due to reason: {}", reason
            )
        except asyncio.QueueFull:
            record_dlq_message("dlq_full_dropped")
            logger.error("Dead Letter Queue is FULL! Dropping overflow message.")

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
                    await self.publish_inbound(msg)
                elif channel == "amberclaw_outbound":
                    msg = _deserialize_outbound(data)
                    await self.publish_outbound(msg)
                elif channel == "amberclaw_system_events":
                    event = _deserialize_system_event(data)
                    await self.publish_system_event(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "Redis Pub/Sub message bus listener encountered an error: {}", e
            )
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe()

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
                logger.warning(
                    "Failed to publish inbound event to Redis: {}. Retrying locally.", e
                )

        if self.inbound.full():
            self._push_to_dlq(msg, reason="inbound_queue_full")
        else:
            await self.inbound.put(msg)
            record_queue_depth("inbound", self.inbound.qsize())

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        self._ensure_redis_listener()
        item = await self.inbound.get()
        record_queue_depth("inbound", self.inbound.qsize())
        return item

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
                logger.warning(
                    "Failed to publish outbound event to Redis: {}. Retrying locally.",
                    e,
                )

        if self.outbound.full():
            self._push_to_dlq(msg, reason="outbound_queue_full")
        else:
            await self.outbound.put(msg)
            record_queue_depth("outbound", self.outbound.qsize())

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        self._ensure_redis_listener()
        item = await self.outbound.get()
        record_queue_depth("outbound", self.outbound.qsize())
        return item

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
                logger.warning(
                    "Failed to publish system event to Redis: {}. Retrying locally.", e
                )

        if self.system_events.full():
            self._push_to_dlq(event, reason="system_events_queue_full")
        else:
            await self.system_events.put(event)
            record_queue_depth("system_events", self.system_events.qsize())

    async def consume_system_event(self) -> SystemEvent:
        """Consume the next system event (blocks until available)."""
        self._ensure_redis_listener()
        item = await self.system_events.get()
        record_queue_depth("system_events", self.system_events.qsize())
        return item

    async def consume_dead_letter_queue(self) -> dict[str, Any]:
        """Consume the next item in the Dead Letter Queue."""
        item = await self.dead_letter_queue.get()
        record_queue_depth("dead_letter_queue", self.dead_letter_queue.qsize())
        return item

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

    @property
    def dead_letter_queue_size(self) -> int:
        """Number of pending items in Dead Letter Queue."""
        return self.dead_letter_queue.qsize()
