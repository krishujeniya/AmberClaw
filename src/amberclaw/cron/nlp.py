# ruff: noqa: PLR0911, PLR0912, PLR2004
"""Natural language schedule parser for Cron subsystem."""

from __future__ import annotations

import re
import time

from amberclaw.cron.types import CronSchedule


def parse_natural_schedule(text: str, tz: str | None = None) -> CronSchedule:
    """Parse a human-readable or cron string into a CronSchedule.

    Supported patterns:
    - Raw cron: "0 9 * * *", "*/15 * * * *"
    - Relative interval: "every 5 minutes", "every 2 hours", "every 30 seconds"
    - Daily at time: "every day at 9am", "every day at 14:30"
    - In future: "in 10 minutes", "in 1 hour"
    """
    clean = text.strip().lower()

    # 1. Raw 5-part cron expression
    parts = clean.split()
    if len(parts) == 5 and all(
        re.match(r"^[\d\*\/\,\-]+$", p) for p in parts
    ):
        return CronSchedule(kind="cron", expr=clean, tz=tz)

    # 2. "every N [seconds|minutes|hours|days]"
    every_match = re.match(r"^every\s+(\d+)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hr|hour|hours|d|day|days)?$", clean)
    if every_match:
        val = int(every_match.group(1))
        unit = (every_match.group(2) or "m").lower()
        if unit.startswith("s"):
            ms = val * 1000
        elif unit.startswith("h"):
            ms = val * 3600 * 1000
        elif unit.startswith("d"):
            ms = val * 86400 * 1000
        else:  # minutes
            ms = val * 60 * 1000
        return CronSchedule(kind="every", every_ms=ms, tz=tz)

    # Simple "every minute", "every hour", "every day"
    if clean in ("every minute", "each minute"):
        return CronSchedule(kind="every", every_ms=60 * 1000, tz=tz)
    if clean in ("every hour", "hourly"):
        return CronSchedule(kind="every", every_ms=3600 * 1000, tz=tz)
    if clean in ("every day", "daily"):
        return CronSchedule(kind="cron", expr="0 0 * * *", tz=tz)

    # 3. "every day at HH[:MM][am|pm]" or "daily at HH[:MM]"
    daily_at_match = re.match(
        r"^(?:every day at|daily at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", clean
    )
    if daily_at_match:
        hour = int(daily_at_match.group(1))
        minute = int(daily_at_match.group(2) or 0)
        ampm = daily_at_match.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        return CronSchedule(kind="cron", expr=f"{minute} {hour} * * *", tz=tz)

    # 4. "in N [minutes|hours]"
    in_match = re.match(r"^in\s+(\d+)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hr|hour|hours)?$", clean)
    if in_match:
        val = int(in_match.group(1))
        unit = (in_match.group(2) or "m").lower()
        now_ms = int(time.time() * 1000)
        if unit.startswith("s"):
            ms = val * 1000
        elif unit.startswith("h"):
            ms = val * 3600 * 1000
        else:
            ms = val * 60 * 1000
        return CronSchedule(kind="at", at_ms=now_ms + ms, tz=tz)

    # Default fallback: assume daily at midnight or raise ValueError
    raise ValueError(f"Unable to parse schedule string: '{text}'")
