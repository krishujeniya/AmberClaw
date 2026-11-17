# ruff: noqa: S101
"""Selective Workflow Migration Adapter (CL-020).

Provides:
- Translation of external workflow schemas (e.g. LangGraph state graphs) into AmberClaw durable DAGs.
- Clear reporting of unsupported nodes without unsafe execution.
- Round-trip fidelity preservation for supported graph structures.
- Strict preservation of security scopes across imported steps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowNodeType(StrEnum):
    TOOL_STEP = "tool_step"
    TRANSFORMATION = "transformation"
    CONDITIONAL_GATE = "conditional_gate"
    HUMAN_APPROVAL_GATE = "human_approval_gate"
    TERMINAL = "terminal"
    UNSUPPORTED = "unsupported"


class MigratedStep(BaseModel):
    step_id: str
    node_type: WorkflowNodeType
    tool_name: str | None = None
    required_scopes: list[str] = Field(default_factory=list)
    idempotent: bool = True
    next_steps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MigrationReport(BaseModel):
    source_framework: str
    source_version: str
    total_nodes_scanned: int
    imported_nodes_count: int
    unsupported_nodes: list[dict[str, str]] = Field(default_factory=list)
    workflow_steps: list[MigratedStep] = Field(default_factory=list)
    is_fully_supported: bool = True


class LangGraphMigrationAdapter:
    """Selective migration adapter translating LangGraph schemas into AmberClaw durable workflows."""

    SUPPORTED_NODE_TYPES = {
        "tool_node": WorkflowNodeType.TOOL_STEP,
        "transform": WorkflowNodeType.TRANSFORMATION,
        "condition": WorkflowNodeType.CONDITIONAL_GATE,
        "approval": WorkflowNodeType.HUMAN_APPROVAL_GATE,
        "end": WorkflowNodeType.TERMINAL,
    }

    def import_from_langgraph(self, graph_dict: dict[str, Any]) -> MigrationReport:
        """Parse external graph dict, convert supported nodes, and flag unsupported ones."""
        nodes = graph_dict.get("nodes", {})
        edges = graph_dict.get("edges", [])
        version = graph_dict.get("schema_version", "unknown")

        steps: list[MigratedStep] = []
        unsupported: list[dict[str, str]] = []

        # Build edge adjacency map
        adj: dict[str, list[str]] = {n_id: [] for n_id in nodes}
        for edge in edges:
            src = edge.get("from")
            dst = edge.get("to")
            if src in adj and dst:
                adj[src].append(dst)

        for node_id, node_def in nodes.items():
            raw_type = node_def.get("type", "unknown")
            if raw_type not in self.SUPPORTED_NODE_TYPES:
                unsupported.append(
                    {
                        "node_id": node_id,
                        "type": raw_type,
                        "reason": f"Node type '{raw_type}' is not supported in private deterministic mode without manual review.",
                    }
                )
                continue

            mapped_type = self.SUPPORTED_NODE_TYPES[raw_type]
            tool_name = node_def.get("tool_name")
            scopes = node_def.get("required_scopes", [])
            idempotent = bool(node_def.get("idempotent", True))

            step = MigratedStep(
                step_id=node_id,
                node_type=mapped_type,
                tool_name=tool_name,
                required_scopes=scopes,
                idempotent=idempotent,
                next_steps=adj.get(node_id, []),
                metadata=node_def.get("metadata", {}),
            )
            steps.append(step)

        return MigrationReport(
            source_framework="LangGraph",
            source_version=version,
            total_nodes_scanned=len(nodes),
            imported_nodes_count=len(steps),
            unsupported_nodes=unsupported,
            workflow_steps=steps,
            is_fully_supported=len(unsupported) == 0,
        )

    def export_to_langgraph(self, report: MigrationReport) -> dict[str, Any]:
        """Round-trip supported steps back into standard LangGraph schema format."""
        reverse_type_map = {v: k for k, v in self.SUPPORTED_NODE_TYPES.items()}
        nodes: dict[str, Any] = {}
        edges: list[dict[str, str]] = []

        for step in report.workflow_steps:
            raw_type = reverse_type_map.get(step.node_type, "tool_node")
            nodes[step.step_id] = {
                "type": raw_type,
                "tool_name": step.tool_name,
                "required_scopes": step.required_scopes,
                "idempotent": step.idempotent,
                "metadata": step.metadata,
            }
            for nxt in step.next_steps:
                edges.append({"from": step.step_id, "to": nxt})

        return {
            "schema_version": report.source_version,
            "nodes": nodes,
            "edges": edges,
        }
