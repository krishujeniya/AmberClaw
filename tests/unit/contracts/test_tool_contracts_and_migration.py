# ruff: noqa: PLR2004
"""Unit tests for CL-020: Typed Tool/Protocol Contracts and Selective Migration."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from amberclaw.agent.contracts.migration_adapter import (
    LangGraphMigrationAdapter,
    WorkflowNodeType,
)
from amberclaw.agent.contracts.tool_contracts import (
    ExecutionScope,
    InsufficientScopeError,
    MalformedToolInputError,
    MalformedToolOutputError,
    ToolContract,
)


class MockFinancialQueryInput(BaseModel):
    account_id: str = Field(min_length=3)
    limit: int = Field(default=10, ge=1, le=100)


class MockFinancialQueryResult(BaseModel):
    account_id: str
    balance_cents: int
    currency: str = "USD"


def test_tool_contract_valid_inputs_and_outputs():
    """Verify tool contract correctly validates well-formed inputs and outputs."""
    contract = ToolContract(
        tool_name="get_account_balance",
        schema_version="1.2.0",
        description="Query account balance",
        execution_scope=ExecutionScope.READ_ONLY,
        required_scopes=["finance:read"],
        input_model=MockFinancialQueryInput,
        output_model=MockFinancialQueryResult,
    )

    # Valid scopes
    contract.validate_caller_scopes(["finance:read", "audit:write"])

    # Valid inputs
    validated_in = contract.validate_inputs({"account_id": "acc_12345", "limit": 25})
    assert validated_in.account_id == "acc_12345"
    assert validated_in.limit == 25

    # Valid output dict
    validated_out = contract.validate_output(
        {"account_id": "acc_12345", "balance_cents": 50000, "currency": "USD"}
    )
    assert validated_out.balance_cents == 50000

    # Valid output JSON string
    json_out = '{"account_id": "acc_12345", "balance_cents": 75000, "currency": "USD"}'
    validated_str = contract.validate_output(json_out)
    assert validated_str.balance_cents == 75000


def test_tool_contract_enforces_auth_scopes():
    """Verify missing required caller scopes raises InsufficientScopeError."""
    contract = ToolContract(
        tool_name="delete_account",
        schema_version="2.0.0",
        description="Irreversible account deletion",
        execution_scope=ExecutionScope.IRREVERSIBLE_SIDE_EFFECT,
        required_scopes=["admin:delete", "compliance:override"],
    )

    with pytest.raises(InsufficientScopeError) as exc_info:
        contract.validate_caller_scopes(["admin:delete"])  # Missing compliance:override
    assert "compliance:override" in str(exc_info.value)


def test_tool_contract_malformed_inputs_fail_predictably():
    """Verify invalid input data raises MalformedToolInputError with structured errors."""
    contract = ToolContract(
        tool_name="get_account_balance",
        input_model=MockFinancialQueryInput,
        output_model=MockFinancialQueryResult,
        description="Test",
    )

    with pytest.raises(MalformedToolInputError) as exc_info:
        contract.validate_inputs({"account_id": "a", "limit": 500})  # Length < 3 and limit > 100
    err_str = str(exc_info.value)
    assert "get_account_balance" in err_str


def test_tool_contract_malformed_outputs_fail_predictably():
    """Verify malformed tool outputs raise MalformedToolOutputError instead of leaking errors."""
    contract = ToolContract(
        tool_name="get_account_balance",
        input_model=MockFinancialQueryInput,
        output_model=MockFinancialQueryResult,
        description="Test",
    )

    # Missing required field 'balance_cents'
    with pytest.raises(MalformedToolOutputError) as exc_info:
        contract.validate_output({"account_id": "acc_999"})
    assert "balance_cents" in str(exc_info.value)

    # Incompatible data type (unparseable string)
    with pytest.raises(MalformedToolOutputError) as exc_info2:
        contract.validate_output(12345)
    assert "incompatible with model" in str(exc_info2.value)


def test_langgraph_migration_adapter_round_trip():
    """Verify supported LangGraph nodes import and export cleanly preserving scopes."""
    adapter = LangGraphMigrationAdapter()

    source_graph = {
        "schema_version": "0.2.1",
        "nodes": {
            "fetch_node": {
                "type": "tool_node",
                "tool_name": "fetch_transactions",
                "required_scopes": ["finance:read"],
                "idempotent": True,
                "metadata": {"timeout": 30},
            },
            "calc_node": {
                "type": "transform",
                "tool_name": "compute_aggregates",
                "required_scopes": ["compute:execute"],
                "idempotent": True,
                "metadata": {},
            },
            "gate_node": {
                "type": "approval",
                "tool_name": "human_reviewer",
                "required_scopes": ["approval:grant"],
                "idempotent": True,
                "metadata": {},
            },
            "finish_node": {
                "type": "end",
                "tool_name": None,
                "required_scopes": [],
                "idempotent": True,
                "metadata": {},
            },
        },
        "edges": [
            {"from": "fetch_node", "to": "calc_node"},
            {"from": "calc_node", "to": "gate_node"},
            {"from": "gate_node", "to": "finish_node"},
        ],
    }

    report = adapter.import_from_langgraph(source_graph)
    assert report.is_fully_supported is True
    assert report.imported_nodes_count == 4
    assert len(report.unsupported_nodes) == 0

    # Step details
    step_map = {s.step_id: s for s in report.workflow_steps}
    assert step_map["fetch_node"].node_type == WorkflowNodeType.TOOL_STEP
    assert step_map["fetch_node"].required_scopes == ["finance:read"]
    assert step_map["calc_node"].next_steps == ["gate_node"]

    # Round-trip export
    exported = adapter.export_to_langgraph(report)
    assert exported["schema_version"] == "0.2.1"
    assert len(exported["nodes"]) == 4
    assert len(exported["edges"]) == 3


def test_langgraph_migration_flags_unsupported_nodes():
    """Verify unsupported arbitrary execution nodes are reported without execution."""
    adapter = LangGraphMigrationAdapter()

    risky_graph = {
        "schema_version": "0.2.1",
        "nodes": {
            "safe_step": {
                "type": "tool_node",
                "tool_name": "read_log",
                "required_scopes": ["logs:read"],
            },
            "eval_step": {
                "type": "dynamic_eval_python",  # Unsupported unsafe node
                "tool_name": "exec_untrusted_code",
            },
        },
        "edges": [{"from": "safe_step", "to": "eval_step"}],
    }

    report = adapter.import_from_langgraph(risky_graph)
    assert report.is_fully_supported is False
    assert report.imported_nodes_count == 1
    assert len(report.unsupported_nodes) == 1
    unsupp = report.unsupported_nodes[0]
    assert unsupp["node_id"] == "eval_step"
    assert "not supported in private deterministic mode" in unsupp["reason"]
