"""Unit tests for the reasoning-reflection and learning loop."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from amberclaw.agent.graph import AgentGraph
from amberclaw.agent.learning_loop import AgentReflector, ReflectionResult


@pytest.mark.asyncio
async def test_agent_reflector_success():
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        '{"is_successful": true, "critique": "The task was successfully done.", '
        '"missing_information": [], "correction_steps": []}'
    )
    mock_provider.chat_with_retry = AsyncMock(return_value=mock_response)

    reflector = AgentReflector(mock_provider)
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]

    result = await reflector.reflect(messages)
    assert isinstance(result, ReflectionResult)
    assert result.is_successful is True
    assert result.critique == "The task was successfully done."
    assert len(result.missing_information) == 0
    assert len(result.correction_steps) == 0


@pytest.mark.asyncio
async def test_agent_reflector_failure():
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        '{"is_successful": false, "critique": "The answer is missing the file content.", '
        '"missing_information": ["File content"], "correction_steps": ["Run read_file on file.txt"]}'
    )
    mock_provider.chat_with_retry = AsyncMock(return_value=mock_response)

    reflector = AgentReflector(mock_provider)
    messages = [
        {"role": "user", "content": "Read file.txt"},
        {"role": "assistant", "content": "I cannot read it without permission."}
    ]

    result = await reflector.reflect(messages)
    assert isinstance(result, ReflectionResult)
    assert result.is_successful is False
    assert "missing" in result.critique
    assert result.missing_information == ["File content"]
    assert result.correction_steps == ["Run read_file on file.txt"]


@pytest.mark.asyncio
async def test_agent_reflector_fallback():
    mock_provider = MagicMock()
    # Bad JSON response triggers fallback
    mock_response = MagicMock()
    mock_response.content = "Not a JSON string"
    mock_provider.chat_with_retry = AsyncMock(return_value=mock_response)

    reflector = AgentReflector(mock_provider)
    result = await reflector.reflect([])
    
    assert isinstance(result, ReflectionResult)
    assert result.is_successful is True
    assert "Reflection failed" in result.critique


@pytest.mark.asyncio
async def test_agent_graph_reflect_node():
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        '{"is_successful": false, "critique": "Fails safety checks.", '
        '"missing_information": [], "correction_steps": ["Retry safely."]}'
    )
    mock_provider.chat_with_retry = AsyncMock(return_value=mock_response)

    graph = AgentGraph(provider=mock_provider, tools=[], mode="react_reflect")
    
    state = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ],
        "iterations": 1,
        "config": {"model": "test-model"},
        "mode": "react_reflect",
        "plan": [],
        "current_task": None,
    }

    result_state = await graph.reflect_node(state)
    assert "messages" in result_state
    ref_msg = result_state["messages"][0]
    assert isinstance(ref_msg, AIMessage)
    assert "Status: FAIL" in ref_msg.content
    assert "Fails safety checks" in ref_msg.content
    assert "Retry safely." in ref_msg.content

    # Test the reflect router detects FAIL
    decision = graph.reflect_router({"messages": [ref_msg], "iterations": 1})
    assert decision == "replan"
