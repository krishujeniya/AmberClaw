"""AmberClaw Core Metrics Interface.

Exposes kernel, message bus, and tool execution Prometheus metrics.
"""

from prometheus_client import Counter, Gauge, Histogram

# Message bus and DLQ metrics
MESSAGE_BUS_QUEUE_DEPTH = Gauge(
    "amberclaw_bus_queue_depth",
    "Current depth of AmberClaw message bus queues",
    ["queue_name"],
)

DLQ_MESSAGES_TOTAL = Counter(
    "amberclaw_dlq_messages_total",
    "Total messages routed to dead letter queue",
    ["reason"],
)

# Kernel services state metric
KERNEL_SERVICE_STATE = Gauge(
    "amberclaw_kernel_service_state",
    "State of managed ClawOS kernel background service (1=running, 0=stopped, -1=failed)",
    ["service_name"],
)

# Tool execution metrics
TOOL_EXECUTION_TOTAL = Counter(
    "amberclaw_tool_execution_total",
    "Total count of tool executions",
    ["tool_name", "status"],
)

TOOL_EXECUTION_LATENCY_SECONDS = Histogram(
    "amberclaw_tool_execution_latency_seconds",
    "Latency of tool execution in seconds",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)


def record_queue_depth(queue_name: str, depth: int) -> None:
    """Record current message bus queue depth."""
    MESSAGE_BUS_QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)


def record_dlq_message(reason: str = "overflow") -> None:
    """Record an overflow or malformed message routed to DLQ."""
    DLQ_MESSAGES_TOTAL.labels(reason=reason).inc()


def set_service_state(service_name: str, is_running: bool, is_failed: bool = False) -> None:
    """Update running state of a kernel background service."""
    if is_failed:
        val = -1
    elif is_running:
        val = 1
    else:
        val = 0
    KERNEL_SERVICE_STATE.labels(service_name=service_name).set(val)


def record_tool_execution(tool_name: str, status: str, duration_seconds: float) -> None:
    """Record tool execution outcome and timing."""
    TOOL_EXECUTION_TOTAL.labels(tool_name=tool_name, status=status).inc()
    TOOL_EXECUTION_LATENCY_SECONDS.labels(tool_name=tool_name).observe(duration_seconds)
