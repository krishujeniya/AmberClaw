"""Offline regression cases for graph data and message boundaries."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from amberclaw.data.agents import (
    DataCleaningAgent,
    DataVisualizationAgent,
    DataWranglingAgent,
    FeatureEngineeringAgent,
    SQLDatabaseAgent,
)
from amberclaw.data.agents._contracts import message_list, text_value
from amberclaw.data.agents.sql_database_agent import (
    MAX_SCHEMA_CHARS,
    _truncate_metadata,
)
from amberclaw.data.agents.workflow_planner_agent import _safe_json_loads
from amberclaw.data.ml_agents.h2o_ml_agent import H2OMLAgent
from amberclaw.data.ml_agents.model_evaluation_agent import _choose_positive_label
from amberclaw.data.multiagents import supervisor_ds_team
from amberclaw.data.multiagents.pandas_data_analyst import PandasDataAnalyst
from amberclaw.data.multiagents.sql_data_analyst import SQLDataAnalyst

MULTIAGENT_SUMMARY_GETTERS = (
    PandasDataAnalyst.get_workflow_summary,
    SQLDataAnalyst.get_workflow_summary,
)
SUMMARY_GETTERS = (
    (DataCleaningAgent.get_workflow_summary, "data_cleaning_agent"),
    (DataWranglingAgent.get_workflow_summary, "data_wrangling_agent"),
    (FeatureEngineeringAgent.get_workflow_summary, "feature_engineering_agent"),
    (DataVisualizationAgent.get_workflow_summary, "data_visualization_agent"),
    (SQLDatabaseAgent.get_workflow_summary, "sql_database_agent"),
    (H2OMLAgent.get_workflow_summary, "h2o_ml_agent"),
    (PandasDataAnalyst.get_workflow_summary, "data_wrangling_agent"),
    (SQLDataAnalyst.get_workflow_summary, "sql_database_agent"),
)


@pytest.mark.parametrize("text", ['["clean", "train"]', 'plan: ["clean", "train"]'])
def test_planner_normalizes_json_array_to_step_mapping(text):
    assert _safe_json_loads(text) == {"steps": ["clean", "train"]}


def test_sql_metadata_serializes_database_dictionary_before_truncation():
    metadata = {"schemas": {"main": {"tables": ["customers"]}}}
    assert json.loads(_truncate_metadata(metadata)) == metadata
    assert _truncate_metadata(None) == ""
    assert _truncate_metadata("x" * (MAX_SCHEMA_CHARS + 1)).endswith("[truncated]")


def test_message_reducer_preserves_ids_and_removes_tool_messages():
    initial = HumanMessage(content="load dataset", id="request")
    replacement = HumanMessage(content="load this dataset", id="request")
    tool = ToolMessage(content="internal", tool_call_id="call")
    tool_calling_ai = AIMessage(
        content="Loaded.",
        tool_calls=[{"name": "load_file", "args": {}, "id": "call"}],
    )
    messages = supervisor_ds_team._supervisor_merge_messages(
        (initial,), (replacement, tool, tool_calling_ai)
    )
    assert [message.content for message in messages] == ["load this dataset", "Loaded."]
    assert messages[0].id == "request"
    assert isinstance(messages[-1], AIMessage)
    assert messages[-1].tool_calls == []
    assert tool_calling_ai.tool_calls  # The reducer must not mutate source messages.


def test_optional_response_fields_are_narrowed_without_coercing_nontext():
    human = HumanMessage(content="request")
    assert message_list(None) == []
    assert message_list("not a message sequence") == []
    assert message_list((human, "not a BaseMessage")) == [human]
    assert text_value("source.py") == "source.py"
    assert text_value({"path": "source.py"}) is None
    assert _choose_positive_label([None, 0, 1]) == "1"


def test_supervisor_loader_registers_requested_local_csv(monkeypatch, tmp_path):
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,total\n1,12\n", encoding="utf-8")
    graph = MagicMock()
    monkeypatch.setattr(supervisor_ds_team, "StateGraph", MagicMock(return_value=graph))
    loader = MagicMock()
    loader.response = {
        "messages": [AIMessage(content="Listed files.")],
        "data_loader_artifacts": {"list_directory_contents": [str(csv_path)]},
    }
    workers = {
        name: MagicMock()
        for name in (
            "data_wrangling_agent",
            "data_cleaning_agent",
            "eda_tools_agent",
            "data_visualization_agent",
            "sql_database_agent",
            "feature_engineering_agent",
            "h2o_ml_agent",
            "mlflow_tools_agent",
            "model_evaluation_agent",
        )
    }
    supervisor_ds_team.make_supervisor_ds_team(
        model=MagicMock(), data_loader_agent=loader, **workers
    )
    nodes = {call.args[0]: call.args[1] for call in graph.add_node.call_args_list}
    result = nodes["Data_Loader_Tools_Agent"](
        {"messages": [HumanMessage(content=f"load {csv_path}")], "artifacts": {}}
    )
    assert result["data_raw"] == {"customer_id": {0: 1}, "total": {0: 12}}
    assert result["active_data_key"] == "data_raw"
    assert result["active_dataset_id"] in result["datasets"]
    assert loader.invoke_messages.call_count == 1


# Call the accessors with a stored response only; graph construction and models are
# irrelevant to report rendering and must not be invoked by these cases.
@pytest.mark.parametrize("getter,_role", SUMMARY_GETTERS)
@pytest.mark.parametrize("messages", [[{"type": "ai", "content": "{}"}], ["wire text"]])
def test_summary_getters_ignore_messages_without_concrete_message_objects(
    getter, _role, messages
):
    response_holder = SimpleNamespace(response={"messages": messages})
    assert getter(response_holder) is None
    assert getter(response_holder, markdown=True) is None


@pytest.mark.parametrize("getter,role", SUMMARY_GETTERS)
@pytest.mark.parametrize("content", ["42", "null", '["step"]', "not JSON"])
def test_summary_getters_guard_nonobject_and_malformed_report_json(
    getter, role, content
):
    response_holder = SimpleNamespace(
        response={"messages": [AIMessage(content=content, role=role)]}
    )
    summary = getter(response_holder)
    if getter in MULTIAGENT_SUMMARY_GETTERS:
        assert content in summary  # Preserve the analyst's plain-text report fallback.
    else:
        assert summary is None


@pytest.mark.parametrize("getter,role", SUMMARY_GETTERS)
@pytest.mark.parametrize("markdown", [False, True])
def test_summary_getters_render_objects_after_normalizing_mixed_message_shapes(
    getter, role, markdown
):
    response_holder = SimpleNamespace(
        response={
            "messages": [
                AIMessage(
                    content='{"report_title": "Verified report", "result": "ready"}',
                    role=role,
                ),
                {"type": "ai", "content": "invalid wire message"},
            ]
        }
    )
    summary = getter(response_holder, markdown=markdown)
    text = summary.data if markdown else summary
    assert "# Verified report" in text
    assert "ready" in text
