# ruff: noqa: PLR2004
"""Unit tests for Cron subsystem extensions: audit, delivery, manager, nlp, and scheduler."""

from pathlib import Path

import pytest

from amberclaw.cron.audit import CronAuditLogger
from amberclaw.cron.delivery import CronDeliveryRouter
from amberclaw.cron.manager import CronManager
from amberclaw.cron.nlp import parse_natural_schedule
from amberclaw.cron.types import CronPayload


def test_parse_natural_schedule():
    # 1. Raw cron expression
    s_cron = parse_natural_schedule("0 9 * * *")
    assert s_cron.kind == "cron"
    assert s_cron.expr == "0 9 * * *"

    # 2. Every interval
    s_every_m = parse_natural_schedule("every 15 minutes")
    assert s_every_m.kind == "every"
    assert s_every_m.every_ms == 15 * 60 * 1000

    s_every_h = parse_natural_schedule("every 2 hours")
    assert s_every_h.kind == "every"
    assert s_every_h.every_ms == 2 * 3600 * 1000

    # 3. Daily at
    s_daily = parse_natural_schedule("every day at 9am")
    assert s_daily.kind == "cron"
    assert s_daily.expr == "0 9 * * *"

    s_daily_pm = parse_natural_schedule("daily at 5:30 pm")
    assert s_daily_pm.kind == "cron"
    assert s_daily_pm.expr == "30 17 * * *"

    # 4. In relative future
    s_in = parse_natural_schedule("in 10 minutes")
    assert s_in.kind == "at"
    assert s_in.at_ms is not None

    # 5. Invalid schedule
    with pytest.raises(ValueError):
        parse_natural_schedule("invalid unknown garbage schedule string")


def test_cron_audit_logger(tmp_path: Path):
    log_file = tmp_path / "cron_audit.jsonl"
    audit = CronAuditLogger(log_path=log_file)

    rec = audit.record_run("job_123", status="ok", duration_ms=45.2)
    assert rec.job_id == "job_123"
    assert rec.status == "ok"
    assert rec.duration_ms == 45.2

    history = audit.get_job_history("job_123")
    assert len(history) == 1
    assert history[0].job_id == "job_123"
    assert log_file.exists()


@pytest.mark.asyncio
async def test_cron_delivery_router():
    router = CronDeliveryRouter()

    # 1. Undelivered payload (no delivery requested)
    p_no_deliver = CronPayload(deliver=False)
    r1 = await router.route_delivery("job_1", p_no_deliver, "Result")
    assert r1.delivered is True
    assert r1.destination == "none"

    # 2. Delivered payload with simulated channel
    p_deliver = CronPayload(deliver=True, channel="telegram", to="123456")
    r2 = await router.route_delivery("job_2", p_deliver, "Job executed successfully")
    assert r2.delivered is True
    assert r2.destination == "telegram://123456"


@pytest.mark.asyncio
async def test_cron_manager_schedule_and_lifecycle(tmp_path: Path):
    store_file = tmp_path / "jobs.json"
    manager = CronManager(workspace_or_store=store_file)

    job = manager.schedule_task(
        name="Morning Report",
        natural_schedule="every 30 minutes",
        message="Generate daily system overview",
        channel="slack",
        to="#general",
    )
    assert job.id is not None
    assert job.name == "Morning Report"
    assert job.schedule.every_ms == 30 * 60 * 1000

    jobs = manager.list_jobs(include_disabled=True)
    assert len(jobs) == 1

    # Disable job
    manager.enable_job(job.id, enabled=False)
    assert manager.list_jobs(include_disabled=False) == []

    # Remove job
    assert manager.remove_job(job.id) is True
    assert manager.list_jobs(include_disabled=True) == []
