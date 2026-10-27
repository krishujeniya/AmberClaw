import pytest
from amberclaw.bus.events import InboundMessage
from amberclaw.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_message_bus_bounded_queue_and_dlq():
    bus = MessageBus(maxsize=2)
    assert bus.maxsize == 2
    assert bus.inbound_size == 0
    assert bus.dead_letter_queue_size == 0

    msg1 = InboundMessage(channel="slack", sender_id="u1", chat_id="c1", content="Hello 1")
    msg2 = InboundMessage(channel="slack", sender_id="u1", chat_id="c1", content="Hello 2")
    msg3 = InboundMessage(channel="slack", sender_id="u1", chat_id="c1", content="Hello 3 (overflow)")

    # Publish 2 messages to fill inbound queue capacity
    await bus.publish_inbound(msg1)
    await bus.publish_inbound(msg2)
    assert bus.inbound_size == 2
    assert bus.dead_letter_queue_size == 0

    # 3rd message overflows inbound queue and must route to DLQ
    await bus.publish_inbound(msg3)
    assert bus.inbound_size == 2
    assert bus.dead_letter_queue_size == 1

    # Consume DLQ
    dlq_item = await bus.consume_dead_letter_queue()
    assert dlq_item["reason"] == "inbound_queue_full"
    assert dlq_item["item"].content == "Hello 3 (overflow)"
