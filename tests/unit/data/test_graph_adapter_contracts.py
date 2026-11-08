"""Offline checks for compiled-graph delegation and provenance boundaries."""

import sys
from collections.abc import AsyncIterator

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from amberclaw.data.templates.agent_templates import AgentGraph, BaseAgent
from amberclaw.data.utils.messages import get_last_user_message_content
from amberclaw.data.utils.pipeline import (
    build_pipeline_snapshot,
    build_reproducible_pipeline_script,
    compute_pipeline_hash,
)
from amberclaw.data.utils.plotly import plotly_from_dict


class GraphState(TypedDict):
    counter: int
    messages: list[AIMessage]


def make_graph(*, checkpoints: bool = False, name: str = "fixture") -> AgentGraph:
    def advance(state: GraphState) -> GraphState:
        return {"counter": state["counter"] + 1, "messages": [AIMessage("done")]}

    graph = StateGraph(GraphState)
    graph.add_node("advance", advance)
    graph.add_edge(START, "advance")
    graph.add_edge("advance", END)
    return graph.compile(
        checkpointer=InMemorySaver() if checkpoints else None, name=name
    )


class ConstructedAgent(BaseAgent):
    def _make_compiled_graph(self) -> AgentGraph:
        return make_graph(name=self._params.get("name", "fixture"))


class ExistingSubclassPattern(BaseAgent):
    """Existing data agents initialize their compiled graph without super()."""

    def __init__(self, *, checkpoints: bool = False) -> None:
        self._compiled_graph = make_graph(checkpoints=checkpoints)
        self.response = None


def test_constructor_delegates_read_only_schema_properties() -> None:
    agent = ConstructedAgent()
    assert agent.input_schema is agent._compiled_graph.input_schema
    assert agent.output_schema is agent._compiled_graph.output_schema
    assert agent.get_response() is None


def test_sync_stream_yields_chunks_and_caches_last_response() -> None:
    agent = ExistingSubclassPattern()
    chunks = list(agent.stream({"counter": 0, "messages": []}, stream_mode="values"))
    assert [chunk["counter"] for chunk in chunks] == [0, 1]
    assert agent.get_response() == chunks[-1]


@pytest.mark.asyncio
async def test_async_stream_is_an_async_iterator() -> None:
    agent = ExistingSubclassPattern()
    stream = agent.astream({"counter": 0, "messages": []}, stream_mode="values")
    assert isinstance(stream, AsyncIterator)
    chunks = [chunk async for chunk in stream]
    assert [chunk["counter"] for chunk in chunks] == [0, 1]
    assert agent.get_response() == chunks[-1]


def test_response_is_optional_before_invocation() -> None:
    agent = ExistingSubclassPattern()
    assert agent.get_response() is None
    initial_counter = 3
    expected_counter = initial_counter + 1
    assert (
        agent.invoke({"counter": initial_counter, "messages": []})["counter"]
        == expected_counter
    )


def test_checkpoint_id_is_supported_for_legacy_before_argument() -> None:
    agent = ExistingSubclassPattern(checkpoints=True)
    config = {"configurable": {"thread_id": "offline-test"}}
    agent.invoke({"counter": 0, "messages": []}, config=config)
    latest = agent.get_state(config)
    checkpoint_id = latest.config["configurable"]["checkpoint_id"]
    history = list(agent.get_state_history(config, before=checkpoint_id))
    assert history
    assert all(
        item.config["configurable"]["checkpoint_id"] != checkpoint_id
        for item in history
    )


@pytest.mark.parametrize("provenance", [None, [], "invalid", {"transform": None}])
def test_pipeline_accepts_missing_or_malformed_optional_provenance(
    provenance: object,
) -> None:
    datasets = {
        "root": {"stage": "raw", "label": "fixture.csv", "provenance": provenance},
        "child": {"stage": "feature", "parent_id": "root", "provenance": provenance},
    }
    assert compute_pipeline_hash(datasets, ["root", "child"])
    script = build_reproducible_pipeline_script(datasets, target_dataset_id="child")
    assert "Final output" in script
    snapshot = build_pipeline_snapshot(datasets, active_dataset_id="child")
    assert snapshot["model_dataset_id"] == "child"


def test_multimodal_user_content_returns_text_blocks() -> None:
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "Describe the image"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,AA=="},
                },
            ]
        ),
        AIMessage(content="old response"),
    ]
    assert get_last_user_message_content(messages) == "Describe the image"


def test_pipeline_infers_function_name_from_recorded_code() -> None:
    datasets = {
        "root": {
            "stage": "raw",
            "provenance": {"source_type": "file", "source": "fixture.csv"},
        },
        "child": {
            "stage": "feature",
            "parent_id": "root",
            "provenance": {
                "transform": {
                    "kind": "python_function",
                    "function_code": "def transform_data(df):\n    return df.copy()",
                }
            },
        },
    }
    script = build_reproducible_pipeline_script(datasets, target_dataset_id="child")
    assert "df = transform_data(df)" in script
    compile(script, "pipeline.py", "exec")


def test_pipeline_all_handles_malformed_creation_timestamp() -> None:
    datasets = {"root": {"created_ts": "unknown", "provenance": None}}
    snapshot = build_pipeline_snapshot(datasets, active_dataset_id="root", target="all")
    assert [item["id"] for item in snapshot["lineage"]] == ["root"]


def test_rebuilt_graph_metadata_and_runnable_composition() -> None:
    agent = ConstructedAgent(name="first")
    old_graph = agent._compiled_graph
    agent.update_params(name="second")
    assert agent.name == "second"
    assert agent.nodes is agent._compiled_graph.nodes
    assert agent.nodes is not old_graph.nodes
    assert agent.InputType == agent._compiled_graph.InputType
    assert agent.OutputType == agent._compiled_graph.OutputType
    assert agent.get_state_keys() == ["counter", "messages"]
    assert set(agent.get_graph().nodes) == {START, "advance", END}
    chain = agent | RunnableLambda(lambda result: result["counter"])
    assert chain.invoke({"counter": 0, "messages": []}) == 1


def test_stream_with_multiple_modes_keeps_tuple_chunks() -> None:
    agent = ExistingSubclassPattern()
    chunks = list(
        agent.stream({"counter": 0, "messages": []}, stream_mode=["updates", "values"])
    )
    assert {mode for mode, _ in chunks} == {"updates", "values"}
    assert agent.get_response() == chunks[-1]


def scalar_agent() -> BaseAgent:
    graph = StateGraph(int)
    graph.add_node("advance", lambda value: value + 1)
    graph.add_edge(START, "advance")
    graph.add_edge("advance", END)
    agent = ExistingSubclassPattern()
    agent._compiled_graph = graph.compile()
    return agent


def test_scalar_graph_output_is_preserved() -> None:
    agent = scalar_agent()
    assert agent.invoke(0) == 1
    assert agent.get_response() == 1
    assert agent.get_state_keys() == []


@pytest.mark.asyncio
async def test_async_scalar_graph_output_is_preserved() -> None:
    agent = scalar_agent()
    assert await agent.ainvoke(0) == 1
    assert agent.get_response() == 1


def test_raw_wire_messages_are_preserved() -> None:
    agent = ExistingSubclassPattern()
    wire_messages = [{"role": "user", "content": "question"}]
    response = agent.invoke(
        {"counter": 0, "messages": wire_messages}, interrupt_before="*"
    )
    assert response["messages"] == wire_messages


def test_plotly_conversion_preserves_optional_dependency_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "plotly", None)
    assert plotly_from_dict(None) is None
    assert plotly_from_dict({"data": []}) is None
