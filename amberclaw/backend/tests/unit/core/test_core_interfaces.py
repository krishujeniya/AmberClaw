# ruff: noqa: ARG002
"""Unit tests for AmberClaw core interface protocols."""

from amberclaw.agent.tools.base import Tool
from amberclaw.channels.base import BaseChannel
from amberclaw.core.interfaces import (
    ChannelInterface,
    ExecutionBackendInterface,
    MemoryInterface,
    ProviderInterface,
    ToolInterface,
)
from amberclaw.memory.session_db import SessionDB
from amberclaw.providers.base import LLMProvider, LLMResponse
from amberclaw.terminal.base import BaseTerminalBackend
from amberclaw.terminal.local import LocalTerminalBackend


class DummyProvider(LLMProvider):
    async def chat(self, messages, tools=None, model=None, **kwargs):
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "mock-model"

    def get_available_models(self) -> list[str]:
        return ["mock-model"]


class DummyChannel(BaseChannel):
    name = "dummy"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send(self, msg) -> None:
        pass


class DummyTool(Tool):
    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "Dummy tool for test"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> str:
        return "done"


def test_provider_interface_protocol():
    provider = DummyProvider()
    assert isinstance(provider, ProviderInterface)


def test_channel_interface_protocol():
    channel = DummyChannel(config={}, bus=None)
    assert isinstance(channel, ChannelInterface)


def test_tool_interface_protocol():
    tool = DummyTool()
    assert isinstance(tool, ToolInterface)


def test_memory_interface_protocol(tmp_path):
    db_path = tmp_path / "test_session.db"
    db = SessionDB(db_path=db_path)
    assert isinstance(db, MemoryInterface)


def test_execution_backend_interface_protocol(tmp_path):
    backend = LocalTerminalBackend(workspace_dir=str(tmp_path))
    assert isinstance(backend, ExecutionBackendInterface)
    assert isinstance(backend, BaseTerminalBackend)
