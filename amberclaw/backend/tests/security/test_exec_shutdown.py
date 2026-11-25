"""Commands owned by an agent must not survive its cancellation."""

import asyncio
import os
import signal
from unittest.mock import AsyncMock, MagicMock

import pytest

from amberclaw.agent.tools.shell import ExecArgs, ExecTool


@pytest.mark.parametrize("timeout", [False, True])
async def test_command_interruption_drains_owned_process(monkeypatch, timeout):
    started = asyncio.Event()

    async def communicate():
        if started.is_set():
            return b"", b""
        started.set()
        await asyncio.Event().wait()
        return b"", b""

    process = MagicMock(pid=12345, returncode=None)
    process.communicate = AsyncMock(side_effect=communicate)
    process.wait = AsyncMock(return_value=0)
    spawn = AsyncMock(return_value=process)
    kill_group = MagicMock()
    monkeypatch.setattr(asyncio, "create_subprocess_shell", spawn)
    monkeypatch.setattr(os, "killpg", kill_group)
    tool = ExecTool(timeout=0 if timeout else 60, restrict_to_workspace=False)
    task = asyncio.create_task(tool.run(ExecArgs(command="echo test")))
    if timeout:
        result = await task
        assert "timed out" in result
    else:
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    if os.name == "posix":
        assert spawn.call_args.kwargs["start_new_session"] is True
        kill_group.assert_called_once_with(process.pid, signal.SIGKILL)
    else:
        process.kill.assert_called_once()
    process.communicate.assert_awaited()
