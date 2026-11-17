"""Tests for unified canonical runtime routing across API, Dashboard, and Channels (CL-004)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from amberclaw.api.deps import get_chat_service
from amberclaw.api.v1.chat import router as chat_router
from amberclaw.schemas.agent import AgentProfile
from amberclaw.services.chat_service import ChatService


class MockAgentStore:
    def __init__(self, agents: dict[str, AgentProfile] | None = None):
        self.agents = agents or {}

    def get(self, agent_id: str) -> AgentProfile | None:
        return self.agents.get(agent_id)


class MockCanonicalRuntime:
    """Mock canonical runtime tracking invocations and streaming tokens."""

    def __init__(self, response_text: str = "Canonical agent execution complete"):
        self.response_text = response_text
        self.invocations: list[dict] = []

    async def process_direct(
        self,
        content: str,
        *,
        session_key: str,
        channel: str,
        chat_id: str,
        on_token=None,
    ) -> str:
        self.invocations.append(
            {
                "content": content,
                "session_key": session_key,
                "channel": channel,
                "chat_id": chat_id,
            }
        )
        if on_token:
            for word in self.response_text.split():
                await on_token(f"{word} ")
        return self.response_text


@pytest.fixture
def app_with_runtime():
    app = FastAPI()
    runtime = MockCanonicalRuntime("Agent runtime response")
    agent_store = MockAgentStore(
        {
            "sec-ops": AgentProfile(name="SecOps", role="Security Auditor"),
            "diag-bot": AgentProfile(name="DiagBot", role="Diagnostic Triage"),
            "agent-alpha": AgentProfile(name="Alpha", role="Operations Engineer"),
        }
    )
    service = ChatService(runtime=runtime, agent_store=agent_store)

    app.include_router(chat_router, prefix="/api/v1/chat")
    app.dependency_overrides[get_chat_service] = lambda: service
    return app, runtime


@pytest.mark.asyncio
async def test_api_chat_routes_through_canonical_runtime(app_with_runtime):
    app, runtime = app_with_runtime
    client = TestClient(app)

    res = client.post(
        "/api/v1/chat",
        json={"message": "Investigate cluster alert #42", "agent_id": "sec-ops"},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["reply"] == "Agent runtime response"
    assert len(runtime.invocations) == 1
    inv = runtime.invocations[0]
    assert inv["content"] == "Investigate cluster alert #42"
    assert inv["session_key"] == "api:sec-ops"
    assert inv["channel"] == "api"
    assert inv["chat_id"] == "sec-ops"


@pytest.mark.asyncio
async def test_api_chat_stream_emits_sse_token_frames_from_runtime(app_with_runtime):
    app, runtime = app_with_runtime
    client = TestClient(app)

    res = client.post(
        "/api/v1/chat/stream",
        json={"message": "Run diagnosis", "agent_id": "diag-bot"},
    )

    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    body = res.text
    assert "event: token" in body
    assert "event: done" in body
    assert len(runtime.invocations) == 1
    assert runtime.invocations[0]["session_key"] == "api:diag-bot"


@pytest.mark.asyncio
async def test_api_raw_completion_bypasses_runtime():
    app = FastAPI()
    runtime = MockCanonicalRuntime("Should not be called")
    service = ChatService(runtime=runtime)

    class MockLLMRouter:
        async def generate(self, messages, model, temperature):
            return "Raw LLM completion"

    service.llm_router = MockLLMRouter()

    app.include_router(chat_router, prefix="/api/v1/chat")
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    res = client.post(
        "/api/v1/chat",
        json={"message": "Hello", "raw_completion": True},
    )

    assert res.status_code == 200
    assert res.json()["reply"] == "Raw LLM completion"
    assert len(runtime.invocations) == 0


@pytest.mark.asyncio
async def test_runtime_parity_across_entry_points():
    runtime = MockCanonicalRuntime("Shared output")
    agent_store = MockAgentStore(
        {"agent-alpha": AgentProfile(name="Alpha", role="Engineer")}
    )

    # Entry Point 1: API
    service = ChatService(runtime=runtime, agent_store=agent_store)
    reply_api, _ = await service.generate_response(
        message="Task 1", agent_id="agent-alpha"
    )
    assert reply_api == "Shared output"

    # Entry Point 2: Direct Agent / CLI invocation
    reply_cli = await runtime.process_direct(
        content="Task 1",
        session_key="cli:direct",
        channel="cli",
        chat_id="direct",
    )
    assert reply_cli == "Shared output"

    # Both entry points dispatch to canonical runtime contract
    assert len(runtime.invocations) == 2
    assert runtime.invocations[0]["channel"] == "api"
    assert runtime.invocations[0]["session_key"] == "api:agent-alpha"
    assert runtime.invocations[1]["channel"] == "cli"
    assert runtime.invocations[1]["session_key"] == "cli:direct"
