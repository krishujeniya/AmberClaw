# ruff: noqa: PLR2004
"""Unit tests for the reasoning-reflection and learning loop."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from amberclaw.agent.graph import AgentGraph
from amberclaw.agent.learning_loop import (
    AgentReflector,
    LearningCycleResult,
    ReflectionResult,
)


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
        {"role": "assistant", "content": "Hi there!"},
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
        {"role": "assistant", "content": "I cannot read it without permission."},
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


@pytest.mark.asyncio
async def test_reflection_cycle_measurable_improvement():
    """Verify that multi-step reflection cycles produce measurable quality improvement."""
    mock_provider = MagicMock()

    # Step 1: Initial reflection (low score)
    resp1 = MagicMock()
    resp1.content = (
        '{"is_successful": false, "quality_score": 0.35, '
        '"critique": "Draft lacks benchmark figures and latency analysis.", '
        '"missing_information": ["Throughput", "p95 latency"], '
        '"correction_steps": ["Run benchmarks", "Include p95 metrics"]}'
    )

    # Step 2: Revised response from LLM
    resp2 = MagicMock()
    resp2.content = (
        "API throughput is 12,500 req/s with p95 latency of 4.2ms under peak load."
    )

    # Step 3: Second reflection (high score after applying correction steps)
    resp3 = MagicMock()
    resp3.content = (
        '{"is_successful": true, "quality_score": 0.95, '
        '"critique": "Response thoroughly covers throughput and latency metrics.", '
        '"missing_information": [], "correction_steps": []}'
    )

    mock_provider.chat_with_retry = AsyncMock(side_effect=[resp1, resp2, resp3])

    reflector = AgentReflector(mock_provider)
    result: LearningCycleResult = await reflector.run_refinement_cycle(
        task="Provide performance benchmarks for the auth API",
        initial_response="The auth API runs fast and handles high load.",
        max_iterations=3,
        target_score=0.90,
    )

    # Assert measurable quality progression
    assert result.initial_score == 0.35
    assert result.final_score == 0.95
    assert result.improvement_delta == 0.60
    assert result.improvement_delta > 0.0  # Measurable improvement proven
    assert result.is_converged is True
    assert result.iterations_count == 2
    assert len(result.trajectory) == 2
    assert result.trajectory[0]["quality_score"] < result.trajectory[1]["quality_score"]
    assert "12,500 req/s" in result.final_response


@pytest.mark.asyncio
async def test_reflection_cycle_early_convergence():
    """Verify early exit when initial output meets target score."""
    mock_provider = MagicMock()
    resp = MagicMock()
    resp.content = (
        '{"is_successful": true, "quality_score": 0.98, '
        '"critique": "Complete and accurate.", "missing_information": [], "correction_steps": []}'
    )
    mock_provider.chat_with_retry = AsyncMock(return_value=resp)

    reflector = AgentReflector(mock_provider)
    result = await reflector.run_refinement_cycle(
        task="List HTTP methods",
        initial_response="GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
        target_score=0.90,
    )

    assert result.iterations_count == 1
    assert result.initial_score == 0.98
    assert result.final_score == 0.98
    assert result.improvement_delta == 0.0
    assert result.is_converged is True
    assert mock_provider.chat_with_retry.call_count == 1


@pytest.mark.asyncio
async def test_reflection_quality_score_auto_calculation():
    """Verify that quality score is computed deterministically if omitted from LLM JSON."""
    mock_provider = MagicMock()
    resp = MagicMock()
    # Missing quality_score field in JSON
    resp.content = (
        '{"is_successful": false, "critique": "Missing details.", '
        '"missing_information": ["item 1", "item 2"], "correction_steps": ["step 1"]}'
    )
    mock_provider.chat_with_retry = AsyncMock(return_value=resp)

    reflector = AgentReflector(mock_provider)
    res = await reflector.reflect([{"role": "user", "content": "test"}])

    assert res.is_successful is False
    assert res.quality_score < 1.0
    assert res.quality_score > 0.0
