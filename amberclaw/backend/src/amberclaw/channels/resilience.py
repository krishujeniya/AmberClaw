# ruff: noqa: ERA001, PLR2004
"""Channel resilience, platform rate limiting, exponential backoff reconnects, and telemetry.

Implements:
- Token-bucket rate limiter per channel with adaptive HTTP 429 backoff handling.
- Reconnect state machine with exponential backoff and jitter.
- Delivery latency, throughput, and error metrics tracker.
"""

import asyncio
import random
import time
from enum import StrEnum
from typing import Any

from loguru import logger

from amberclaw.channels.capabilities import get_channel_capability


class ConnectionState(StrEnum):
    """Lifecycle state of a channel platform connection."""

    CONNECTED = "connected"
    CONNECTING = "connecting"
    BACKOFF = "backoff"
    FAILED = "failed"


class ChannelRateLimiter:
    """Thread-safe token-bucket rate limiter for messaging platforms."""

    def __init__(self) -> None:
        # {channel: (tokens, last_refill_timestamp)}
        self._buckets: dict[str, tuple[float, float]] = {}
        # {channel: blocked_until_timestamp}
        self._rate_limited_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self, channel: str, cost: float = 1.0, timeout: float = 5.0
    ) -> bool:
        """Attempt to acquire tokens to send a message on channel.

        Waits asynchronously up to `timeout` seconds if tokens are depleted.
        """
        start = time.monotonic()
        cap = get_channel_capability(channel)
        refill_rate = cap.rate_limit_messages_per_sec
        capacity = max(refill_rate * 2.0, 5.0)

        while time.monotonic() - start < timeout:
            async with self._lock:
                now = time.monotonic()

                # Check if currently blocked by explicit 429 Retry-After
                blocked_until = self._rate_limited_until.get(channel, 0.0)
                if now < blocked_until:
                    wait_needed = blocked_until - now
                    if wait_needed > timeout - (time.monotonic() - start):
                        return False
                    await asyncio.sleep(min(wait_needed, 0.5))
                    continue

                tokens, last_refill = self._buckets.get(channel, (capacity, now))
                # Add refilled tokens
                elapsed = now - last_refill
                tokens = min(capacity, tokens + (elapsed * refill_rate))

                if tokens >= cost:
                    self._buckets[channel] = (tokens - cost, now)
                    return True

            # Sleep briefly and retry
            await asyncio.sleep(0.05)

        logger.warning(
            "Channel '{}' rate limit acquire timed out ({}s)", channel, timeout
        )
        return False

    def report_rate_limit(
        self, channel: str, retry_after_sec: float | None = None
    ) -> None:
        """Notify limiter of a platform 429 response to initiate backoff."""
        delay = (
            retry_after_sec
            if (retry_after_sec is not None and retry_after_sec > 0)
            else 5.0
        )
        self._rate_limited_until[channel] = time.monotonic() + delay
        logger.warning(
            "Channel '{}' rate-limited by upstream platform. Pausing dispatch for {}s",
            channel,
            delay,
        )

    def is_blocked(self, channel: str) -> bool:
        """Check if channel is actively cooling down from a 429."""
        return time.monotonic() < self._rate_limited_until.get(channel, 0.0)

    def clear(self) -> None:
        self._buckets.clear()
        self._rate_limited_until.clear()


class ChannelReconnectManager:
    """State machine governing channel reconnections with exponential backoff and jitter."""

    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter_ratio: float = 0.2,
    ) -> None:
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter_ratio = jitter_ratio
        # {channel: failure_count}
        self._failures: dict[str, int] = {}
        # {channel: ConnectionState}
        self._states: dict[str, ConnectionState] = {}

    def get_state(self, channel: str) -> ConnectionState:
        return self._states.get(channel, ConnectionState.CONNECTED)

    def set_state(self, channel: str, state: ConnectionState) -> None:
        self._states[channel] = state

    def record_failure(self, channel: str) -> float:
        """Record a connection failure and compute next backoff delay in seconds."""
        failures = self._failures.get(channel, 0) + 1
        self._failures[channel] = failures
        self._states[channel] = ConnectionState.BACKOFF

        base_delay = min(
            self.max_delay, self.initial_delay * (self.multiplier ** (failures - 1))
        )
        # Apply jitter
        jitter = base_delay * self.jitter_ratio * (random.random() * 2 - 1)  # noqa: S311
        actual_delay = max(0.1, base_delay + jitter)

        logger.warning(
            "Channel '{}' connection failure #{}. Backing off for {:.2f}s",
            channel,
            failures,
            actual_delay,
        )
        return actual_delay

    def record_success(self, channel: str) -> None:
        """Record successful connection or recovery."""
        self._failures[channel] = 0
        self._states[channel] = ConnectionState.CONNECTED

    def should_retry(self, channel: str, max_retries: int = 5) -> bool:
        """Check if reconnect attempts remain within acceptable threshold."""
        failures = self._failures.get(channel, 0)
        if failures >= max_retries:
            self._states[channel] = ConnectionState.FAILED
            logger.error(
                "Channel '{}' exceeded maximum reconnect retries ({}/{}). State: FAILED",
                channel,
                failures,
                max_retries,
            )
            return False
        return True

    def clear(self) -> None:
        self._failures.clear()
        self._states.clear()


class ChannelMetricsTracker:
    """Records delivery latency, error rates, and message throughput per channel."""

    def __init__(self) -> None:
        # {channel: [latency_ms, ...]}
        self._latencies: dict[str, list[float]] = {}
        self._sent_counts: dict[str, int] = {}
        self._failed_counts: dict[str, int] = {}
        self._inbound_counts: dict[str, int] = {}
        self._reconnects: dict[str, int] = {}

    def record_delivery(self, channel: str, duration_ms: float, success: bool) -> None:
        """Record the outcome and latency of an outbound message send."""
        if channel not in self._latencies:
            self._latencies[channel] = []
        self._latencies[channel].append(duration_ms)
        if len(self._latencies[channel]) > 1000:
            self._latencies[channel] = self._latencies[channel][-1000:]

        if success:
            self._sent_counts[channel] = self._sent_counts.get(channel, 0) + 1
        else:
            self._failed_counts[channel] = self._failed_counts.get(channel, 0) + 1

    def record_inbound(self, channel: str) -> None:
        self._inbound_counts[channel] = self._inbound_counts.get(channel, 0) + 1

    def record_reconnect(self, channel: str) -> None:
        self._reconnects[channel] = self._reconnects.get(channel, 0) + 1

    def get_stats(self, channel: str) -> dict[str, Any]:
        """Compute summary statistics for a specific channel."""
        lats = sorted(self._latencies.get(channel, []))
        total_outbound = self._sent_counts.get(channel, 0) + self._failed_counts.get(
            channel, 0
        )
        success_rate = (
            (self._sent_counts.get(channel, 0) / total_outbound)
            if total_outbound > 0
            else 1.0
        )

        def _percentile(data: list[float], p: float) -> float:
            if not data:
                return 0.0
            idx = int(len(data) * p)
            return data[min(idx, len(data) - 1)]

        return {
            "channel": channel,
            "messages_sent": self._sent_counts.get(channel, 0),
            "messages_failed": self._failed_counts.get(channel, 0),
            "messages_received": self._inbound_counts.get(channel, 0),
            "success_rate": round(success_rate, 4),
            "reconnect_events": self._reconnects.get(channel, 0),
            "latency_p50_ms": round(_percentile(lats, 0.50), 2),
            "latency_p95_ms": round(_percentile(lats, 0.95), 2),
            "latency_p99_ms": round(_percentile(lats, 0.99), 2),
        }

    def clear(self) -> None:
        self._latencies.clear()
        self._sent_counts.clear()
        self._failed_counts.clear()
        self._inbound_counts.clear()
        self._reconnects.clear()
