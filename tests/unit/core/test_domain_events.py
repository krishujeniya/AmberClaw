# ruff: noqa: PLR2004, ERA001, PLW0108, PLC0415
"""Unit tests for typed domain events, DomainEventBus, and telemetry context."""

import asyncio

import pytest

from amberclaw.core.events import (
    AgentCreatedEvent,
    AgentDeletedEvent,
    DomainEventBus,
    DomainEventType,
    Event,
    MemoryMutationEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    TicketCreatedEvent,
    TicketResolvedEvent,
    ToolExecutedEvent,
)
from amberclaw.core.metrics import (
    record_dlq_message,
    record_queue_depth,
    record_tool_execution,
    set_service_state,
)
from amberclaw.core.telemetry import (
    get_correlation_id,
    set_correlation_id,
    trace_span,
    traced,
)


def test_domain_event_instantiation_defaults():
    evt = AgentCreatedEvent(
        agent_id="agent_007",
        name="Bond",
        model_name="gpt-4o",
        role="Intelligence Agent",
    )
    assert evt.event_id.startswith("evt_")
    assert evt.event_type == DomainEventType.AGENT_CREATED.value
    assert evt.version == "1.0"
    assert evt.agent_id == "agent_007"
    assert evt.name == "Bond"
    assert evt.correlation_id.startswith("corr_")


def test_all_typed_events():
    t_del = AgentDeletedEvent(agent_id="agent_123")
    assert t_del.event_type == "agent.deleted"

    t_start = TaskStartedEvent(task_id="t1", agent_id="a1", session_id="s1")
    assert t_start.event_type == "task.started"

    t_done = TaskCompletedEvent(
        task_id="t1", agent_id="a1", status="success", duration_s=1.2
    )
    assert t_done.event_type == "task.completed"

    t_tool = ToolExecutedEvent(
        tool_name="bash", agent_id="a1", status="success", duration_s=0.05
    )
    assert t_tool.event_type == "tool.executed"

    t_tix_c = TicketCreatedEvent(
        ticket_id="tix_1", requester_id="a1", description="Need sudo"
    )
    assert t_tix_c.event_type == "ticket.created"

    t_tix_r = TicketResolvedEvent(
        ticket_id="tix_1", status="approved", reviewer_id="admin"
    )
    assert t_tix_r.event_type == "ticket.resolved"

    t_mem = MemoryMutationEvent(action="add_turn", session_id="s1", count=1)
    assert t_mem.event_type == "memory.mutation"


@pytest.mark.asyncio
async def test_domain_event_bus_exact_and_wildcard():
    bus = DomainEventBus()
    received_agent_events = []
    received_all_events = []
    received_task_events = []

    bus.subscribe("agent.created", lambda e: received_agent_events.append(e))
    bus.subscribe("agent.*", lambda e: received_agent_events.append(e))
    bus.subscribe("*", lambda e: received_all_events.append(e))
    bus.subscribe("task.*", lambda e: received_task_events.append(e))

    # Emit agent.created
    agent_evt = AgentCreatedEvent(
        agent_id="a1", name="Alpha", model_name="claude-3-5-sonnet"
    )
    count = await bus.emit(agent_evt)
    # Matches: exact "agent.created", wildcard "agent.*", and global "*"
    assert count == 3
    assert len(received_agent_events) == 2
    assert len(received_all_events) == 1
    assert len(received_task_events) == 0

    # Emit task.started
    task_evt = TaskStartedEvent(task_id="t1", agent_id="a1")
    count2 = await bus.emit(task_evt)
    # Matches: "task.*" and "*"
    assert count2 == 2
    assert len(received_task_events) == 1
    assert len(received_all_events) == 2


@pytest.mark.asyncio
async def test_domain_event_bus_legacy_event():
    bus = DomainEventBus()
    received = []
    bus.subscribe("custom.legacy", lambda e: received.append(e))

    legacy = Event(name="custom.legacy", payload={"key": "val"})
    await bus.emit(legacy)
    assert len(received) == 1
    assert received[0].name == "custom.legacy"


def test_telemetry_correlation_id_propagation():
    set_correlation_id("test-correlation-12345")
    assert get_correlation_id() == "test-correlation-12345"

    with trace_span("test_operation", {"user": "alice"}) as ctx:
        assert ctx["attributes"]["correlation_id"] == "test-correlation-12345"
        assert ctx["attributes"]["user"] == "alice"


@pytest.mark.asyncio
async def test_traced_decorator():
    @traced(name="async_sample_op")
    async def sample_async_func(x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2

    res = await sample_async_func(21)
    assert res == 42


def test_core_metrics_recording():
    record_queue_depth("inbound", 42)
    record_dlq_message("overflow_test")
    set_service_state("agent_loop", is_running=True)
    set_service_state("failed_service", is_running=False, is_failed=True)
    record_tool_execution("exec_bash", "success", 0.12)


@pytest.mark.asyncio
async def test_message_bus_metrics_integration():
    from amberclaw.bus.events import InboundMessage
    from amberclaw.bus.queue import MessageBus
    from amberclaw.core.metrics import DLQ_MESSAGES_TOTAL, MESSAGE_BUS_QUEUE_DEPTH

    bus = MessageBus(maxsize=1)
    msg1 = InboundMessage(channel="cli", sender_id="u1", chat_id="c1", content="hello")
    await bus.publish_inbound(msg1)
    assert MESSAGE_BUS_QUEUE_DEPTH.labels(queue_name="inbound")._value.get() == 1

    # Overflow to DLQ
    msg2 = InboundMessage(
        channel="cli", sender_id="u2", chat_id="c1", content="overflow"
    )
    dlq_before = DLQ_MESSAGES_TOTAL.labels(reason="inbound_queue_full")._value.get()
    await bus.publish_inbound(msg2)
    dlq_after = DLQ_MESSAGES_TOTAL.labels(reason="inbound_queue_full")._value.get()
    assert dlq_after == dlq_before + 1

    consumed = await bus.consume_inbound()
    assert consumed.content == "hello"
    assert MESSAGE_BUS_QUEUE_DEPTH.labels(queue_name="inbound")._value.get() == 0


@pytest.mark.asyncio
async def test_supervisor_metrics_integration(tmp_path):
    from amberclaw.bus.queue import MessageBus
    from amberclaw.core.kernel import ClawOSSupervisor
    from amberclaw.core.metrics import KERNEL_SERVICE_STATE

    bus = MessageBus()
    supervisor = ClawOSSupervisor(bus=bus, workspace=tmp_path)

    async def dummy_start():
        await asyncio.sleep(0.01)

    def dummy_stop():
        pass

    supervisor.register_service("test_svc", dummy_start, dummy_stop)
    assert KERNEL_SERVICE_STATE.labels(service_name="test_svc")._value.get() == 0

    await supervisor.start()
    assert KERNEL_SERVICE_STATE.labels(service_name="test_svc")._value.get() == 1

    await supervisor.stop()
    assert KERNEL_SERVICE_STATE.labels(service_name="test_svc")._value.get() == 0
