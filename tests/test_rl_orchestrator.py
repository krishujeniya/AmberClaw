import asyncio
import sys

import pytest

from amberclaw.rl.orchestrator import RLOrchestrator, RLProcessConfig, RLProcessType


@pytest.mark.asyncio
async def test_rl_orchestrator_lifecycle():
    orchestrator = RLOrchestrator()
    py_bin = sys.executable or "python"

    # Override delays for testing so we don't wait 90 seconds
    orchestrator.configs = [
        RLProcessConfig(
            name=RLProcessType.ATROPOS_API,
            command=[py_bin, "-c", "import time; time.sleep(10)"],
            delay_sec=0,
        ),
        RLProcessConfig(
            name=RLProcessType.ENVIRONMENT_SERVER,
            command=[py_bin, "-c", "import time; time.sleep(10)"],
            delay_sec=0,
        ),
    ]

    await orchestrator.start_all()

    # Give event loop a moment to start the processes
    await asyncio.sleep(0.5)

    assert len(orchestrator.processes) == 2
    for proc in orchestrator.processes.values():
        assert proc.returncode is None  # Process is running

    await orchestrator.stop_all()

    assert len(orchestrator.processes) == 0
    assert orchestrator._is_running is False
