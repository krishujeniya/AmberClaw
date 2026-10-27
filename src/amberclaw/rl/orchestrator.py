import asyncio
import contextlib
import sys
from enum import StrEnum

from loguru import logger
from pydantic import BaseModel, Field


class RLProcessType(StrEnum):
    ATROPOS_API = "atropos_api"
    ENVIRONMENT_SERVER = "environment_server"
    TINKER_TRAINER = "tinker_trainer"


class RLProcessConfig(BaseModel):
    """Configuration for an RL orchestrated process."""

    name: RLProcessType
    command: list[str]
    delay_sec: int = Field(default=0, description="Delay before starting this process.")


class RLOrchestrator:
    """Automates staggered startup and management of the RL training pipeline processes."""

    def __init__(self) -> None:
        self.processes: dict[RLProcessType, asyncio.subprocess.Process] = {}
        py_bin = sys.executable or "python"
        self.configs: list[RLProcessConfig] = [
            RLProcessConfig(
                name=RLProcessType.ATROPOS_API,
                command=[py_bin, "-m", "amberclaw.rl.mock_server", "--type", "api"],
                delay_sec=0,
            ),
            RLProcessConfig(
                name=RLProcessType.ENVIRONMENT_SERVER,
                command=[py_bin, "-m", "amberclaw.rl.mock_server", "--type", "env"],
                delay_sec=5,
            ),
            RLProcessConfig(
                name=RLProcessType.TINKER_TRAINER,
                command=[
                    py_bin,
                    "-m",
                    "amberclaw.rl.mock_server",
                    "--type",
                    "tinker",
                    "--port",
                    "8001",
                ],
                delay_sec=30,
            ),
        ]
        self._tasks: list[asyncio.Task] = []
        self._monitor_tasks: list[asyncio.Task] = []
        self._is_running = False

    async def _run_process(self, config: RLProcessConfig) -> None:
        """Wait for delay and then launch the process."""
        if config.delay_sec > 0:
            logger.info(
                f"Waiting {config.delay_sec}s before starting {config.name.value}..."
            )
            await asyncio.sleep(config.delay_sec)

        if not self._is_running:
            return

        logger.info(f"Starting process: {config.name.value}")
        try:
            process = await asyncio.create_subprocess_exec(
                *config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.processes[config.name] = process
            logger.info(f"Process {config.name.value} started with PID {process.pid}")

            m_task = asyncio.create_task(self._monitor_output(config.name, process))
            self._monitor_tasks.append(m_task)

            await process.wait()
            logger.warning(
                f"Process {config.name.value} exited with code {process.returncode}"
            )
        except asyncio.CancelledError:
            logger.info(f"Startup task for {config.name.value} cancelled.")
        except Exception as ex:
            logger.error(f"Failed to start process {config.name.value}: {ex}")

    async def _monitor_output(
        self, name: RLProcessType, process: asyncio.subprocess.Process
    ) -> None:
        """Stream process stdout/stderr to logger."""
        if not process.stdout or not process.stderr:
            return

        async def read_stream(stream: asyncio.StreamReader, is_error: bool) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                if is_error:
                    logger.debug(f"[{name.value} ERR] {decoded}")
                else:
                    logger.debug(f"[{name.value} OUT] {decoded}")

        await asyncio.gather(
            read_stream(process.stdout, False),
            read_stream(process.stderr, True),
        )

    async def start_all(self) -> None:
        """Launch all configured RL processes with their respective delays."""
        self._is_running = True
        logger.info("Initializing RL Three-Process Orchestration...")
        for config in self.configs:
            task = asyncio.create_task(self._run_process(config))
            self._tasks.append(task)

    async def stop_all(self) -> None:
        """Terminate all managed processes gracefully."""
        self._is_running = False
        logger.info("Stopping all RL processes...")

        # Cancel pending startup tasks
        for task in self._tasks + self._monitor_tasks:
            if not task.done():
                task.cancel()

        # Terminate running processes
        for name, process in self.processes.items():
            if process.returncode is None:
                logger.info(f"Terminating {name.value} (PID {process.pid})...")
                with contextlib.suppress(ProcessLookupError):
                    process.terminate()

        # Wait for processes to exit
        for name, process in self.processes.items():
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except TimeoutError:
                    logger.warning(
                        f"Process {name.value} did not terminate gracefully, killing..."
                    )
                    with contextlib.suppress(ProcessLookupError):
                        process.kill()

        self.processes.clear()
        self._tasks.clear()
        self._monitor_tasks.clear()
        logger.info("All RL processes stopped.")
