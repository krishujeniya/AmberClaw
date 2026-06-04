"""AmberClaw ClawOS Kernel Supervisor.

Orchestrates background processes (AgentLoop, CronService), monitors system health,
and handles auto-recovery and event bus propagation of system events.
"""

import asyncio
import contextlib
import os
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

from amberclaw.bus.events import InboundMessage, SystemEvent
from amberclaw.bus.queue import MessageBus


class ClawOSSupervisor:
    """ClawOS Supervisor to manage services, monitor health, and route system events."""

    def __init__(
        self,
        bus: MessageBus,
        workspace: Path,
        config: Any | None = None,
        check_interval_s: float = 5.0,
    ) -> None:
        self.bus = bus
        self.workspace = workspace
        self.config = config
        self.check_interval_s = check_interval_s
        self._services: dict[str, dict[str, Any]] = {}
        self._running = False
        self._supervisor_task: asyncio.Task | None = None
        self._event_listener_task: asyncio.Task | None = None
        self._health_monitor_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def register_service(
        self,
        name: str,
        start_fn: Callable[[], Coroutine[Any, Any, None]],
        stop_fn: Callable[[], None] | Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a background service with its start and stop functions."""
        self._services[name] = {
            "name": name,
            "start_fn": start_fn,
            "stop_fn": stop_fn,
            "task": None,
            "status": "stopped",
            "restarts": 0,
            "last_restart_time": 0.0,
        }
        logger.info("Supervisor: Registered service '{}'", name)

    async def start(self) -> None:
        """Start the supervisor and all registered services."""
        async with self._lock:
            if self._running:
                return
            self._running = True
            logger.info("Supervisor: Starting ClawOS Supervisor...")

            # Start all services
            for name in list(self._services.keys()):
                await self._start_service_locked(name)

            # Start supervisor core loops
            self._supervisor_task = asyncio.create_task(self._supervisor_loop())
            self._event_listener_task = asyncio.create_task(
                self._event_listener_loop(),
            )
            self._health_monitor_task = asyncio.create_task(
                self._health_monitor_loop(),
            )
            logger.info("Supervisor: ClawOS Supervisor started successfully.")

    async def stop(self) -> None:
        """Stop the supervisor and all managed services."""
        async with self._lock:
            if not self._running:
                return
            self._running = False
            logger.info("Supervisor: Stopping ClawOS Supervisor...")

            # Cancel background loops
            for task in [
                self._supervisor_task,
                self._event_listener_task,
                self._health_monitor_task,
            ]:
                if task:
                    task.cancel()

            # Stop all services
            tasks_to_wait = []
            for name, svc in self._services.items():
                logger.info("Supervisor: Stopping service '{}'", name)
                try:
                    res = svc["stop_fn"]()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    logger.error(
                        "Supervisor: Error stopping service '{}': {}",
                        name,
                        e,
                    )

                task = svc["task"]
                if task and not task.done():
                    task.cancel()
                    tasks_to_wait.append(task)
                svc["status"] = "stopped"
                svc["task"] = None

            # Wait for all service tasks to complete/terminate
            if tasks_to_wait:
                await asyncio.gather(*tasks_to_wait, return_exceptions=True)

            logger.info("Supervisor: ClawOS Supervisor stopped.")

    async def restart_service(self, name: str) -> None:
        """Manually trigger a service restart."""
        async with self._lock:
            if name not in self._services:
                raise ValueError(f"Service '{name}' is not registered.")
            logger.info("Supervisor: Manual restart requested for '{}'", name)
            await self._stop_service_locked(name)
            await self._start_service_locked(name)

    async def _start_service_locked(self, name: str) -> None:
        """Start a service, assuming lock is acquired."""
        svc = self._services[name]
        if svc["status"] == "running":
            return

        logger.info("Supervisor: Starting service '{}'...", name)
        svc["status"] = "running"

        async def _run_wrapper():
            try:
                await svc["start_fn"]()
            except asyncio.CancelledError:
                logger.debug("Supervisor: Service '{}' cancelled", name)
                raise
            except Exception as e:
                logger.exception("Supervisor: Service '{}' raised an error", name)
                raise e
            finally:
                logger.info("Supervisor: Service '{}' exited run wrapper", name)

        svc["task"] = asyncio.create_task(_run_wrapper())

    async def _stop_service_locked(self, name: str) -> None:
        """Stop a service, assuming lock is acquired."""
        svc = self._services[name]
        logger.info("Supervisor: Stopping service '{}'...", name)
        try:
            res = svc["stop_fn"]()
            if asyncio.iscoroutine(res):
                await res
        except Exception as e:
            logger.error("Supervisor: Error calling stop on '{}': {}", name, e)

        task = svc["task"]
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        svc["status"] = "stopped"
        svc["task"] = None

    async def _supervisor_loop(self) -> None:
        """Periodic loop to monitor and restart failed services."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval_s)
                async with self._lock:
                    for name, svc in self._services.items():
                        task = svc["task"]
                        if (
                            svc["status"] == "running"
                            and (task is None or task.done())
                        ):
                            # Service crashed or exited unexpectedly
                            exc = (
                                task.exception()
                                if task and task.done() and not task.cancelled()
                                else None
                            )
                            err_msg = (
                                f"Service '{name}' crashed with: {exc!r}"
                                if exc
                                else f"Service '{name}' stopped unexpectedly."
                            )
                            logger.error("Supervisor: {}", err_msg)

                            svc["status"] = "failed"

                            # Publish failure event
                            await self.bus.publish_system_event(
                                SystemEvent(
                                    event_type="service_failure",
                                    severity="critical",
                                    message=err_msg,
                                    details={
                                        "service": name,
                                        "error": str(exc) if exc else None,
                                    },
                                ),
                            )

                            # Attempt auto-recovery
                            now = time.time()
                            max_restarts = 5
                            cooldown_period_s = 60.0
                            # Prevent fast crash-loops
                            if (
                                now - svc["last_restart_time"]
                                > cooldown_period_s
                            ):
                                svc["restarts"] = 0

                            if svc["restarts"] < max_restarts:
                                svc["restarts"] += 1
                                svc["last_restart_time"] = now
                                logger.warning(
                                    "Supervisor: Auto-restarting service '{}'"
                                    " (attempt {}/5)",
                                    name,
                                    svc["restarts"],
                                )
                                await self._start_service_locked(name)
                            else:
                                logger.error(
                                    "Supervisor: Service '{}' reached maximum"
                                    " restart limit. Manual intervention required.",
                                    name,
                                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Supervisor: Error in supervisor loop: {}", e)

    async def _event_listener_loop(self) -> None:
        """Listens for system events and wakes up the agent loop."""
        while self._running:
            try:
                event = await self.bus.consume_system_event()
                logger.info(
                    "Supervisor: Received SystemEvent: {} [{}]",
                    event.event_type,
                    event.severity,
                )

                # Route critical alerts to the Inbound Queue
                if event.severity in {"warning", "critical"}:
                    alert_content = (
                        f"[SYSTEM ALERT] Type: {event.event_type}\n"
                        f"Severity: {event.severity}\n"
                        f"Message: {event.message}"
                    )
                    msg = InboundMessage(
                        channel="system",
                        sender_id="supervisor",
                        chat_id="system",
                        content=alert_content,
                        metadata={"system_event_type": event.event_type},
                    )
                    await self.bus.publish_inbound(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Supervisor: Error in system event listener: {}", e)

    async def run_diagnostics(self) -> None:
        """Run machine-readable system diagnostic checks."""
        # 1. Check workspace existence and permissions
        try:
            if not self.workspace.exists():
                logger.error(
                    "Supervisor Health Check: Workspace path does not exist: {}",
                    self.workspace,
                )
                await self.bus.publish_system_event(
                    SystemEvent(
                        event_type="workspace_invalid",
                        severity="critical",
                        message=f"Workspace path does not exist: {self.workspace}",
                    ),
                )
            else:
                # Test write access
                test_file = self.workspace / ".health_check_write_test"
                try:
                    test_file.touch()
                    test_file.unlink()
                except Exception as e:
                    logger.error(
                        "Supervisor Health Check: Workspace not writeable: {}",
                        e,
                    )
                    await self.bus.publish_system_event(
                        SystemEvent(
                            event_type="workspace_invalid",
                            severity="critical",
                            message=f"Workspace path is not writeable: {e}",
                        ),
                    )
        except Exception as e:
            logger.error("Supervisor Health Check: Failed to check workspace: {}", e)

        # 2. Check API Keys (ClawDoctor style)
        has_any_key = False
        api_keys = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "DEEPSEEK_API_KEY",
            "GROQ_API_KEY",
        ]
        for key in api_keys:
            if os.getenv(key):
                has_any_key = True
                break

        # Also check in config providers
        if not has_any_key and self.config:
            try:
                providers = [
                    "openai",
                    "anthropic",
                    "gemini",
                    "google",
                    "deepseek",
                    "groq",
                ]
                for p_name in providers:
                    p = getattr(self.config.providers, p_name, None)
                    if p and getattr(p, "api_key", None):
                        has_any_key = True
                        break
            except Exception as e:
                logger.debug("Supervisor Health Check: Error checking providers: {}", e)

        if not has_any_key:
            logger.warning("Supervisor Health Check: No API keys configured.")
            await self.bus.publish_system_event(
                SystemEvent(
                    event_type="api_key_missing",
                    severity="warning",
                    message=(
                        "No LLM API keys found in environment or config. "
                        "Requests will fail."
                    ),
                ),
            )

    async def _health_monitor_loop(self) -> None:
        """Periodically checks system resources and publishes events."""
        memory_threshold = 90.0
        while self._running:
            try:
                # Run diagnostic checks
                await self.run_diagnostics()

                # Check memory
                mem = psutil.virtual_memory()
                if mem.percent > memory_threshold:
                    logger.warning(
                        "Supervisor: High memory usage detected: {}%",
                        mem.percent,
                    )
                    details = {
                        "percent": mem.percent,
                        "available_mb": mem.available / (1024 * 1024),
                    }
                    message_text = (
                        "System memory usage is extremely high "
                        f"({mem.percent}%)."
                    )
                    await self.bus.publish_system_event(
                        SystemEvent(
                            event_type="low_memory",
                            severity="warning",
                            message=message_text,
                            details=details,
                        ),
                    )

                # check health less frequently
                await asyncio.sleep(self.check_interval_s * 4)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Supervisor: Error in health monitor loop: {}", e)
