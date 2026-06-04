# ruff: noqa: E501
"""Temporal Graph Memory for AmberClaw.

Implements a hybrid vector + knowledge graph memory store tracking time-aware
fact changes, entity types, and multi-hop relationships.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx
from loguru import logger


class TemporalGraphMemory:
    """Temporal Graph Memory managing entities, relationships, and history."""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            self.db_path = Path("~/.amberclaw/workspace/graph_memory.json").expanduser()
        else:
            self.db_path = Path(db_path)

        self.graph = nx.MultiDiGraph()
        self.load()

    def load(self) -> None:
        """Load graph from disk if it exists."""
        if not self.db_path.exists():
            logger.info("No existing graph memory found. Initializing empty graph.")
            return

        try:
            with self.db_path.open(encoding="utf-8") as f:
                data = json.load(f)

            # Load nodes
            for node_id, attrs in data.get("nodes", {}).items():
                self.graph.add_node(node_id, **attrs)

            # Load edges
            for edge in data.get("edges", []):
                self.graph.add_edge(
                    edge["source"],
                    edge["target"],
                    key=edge.get("key"),
                    relation=edge.get("relation"),
                    created_at=edge.get("created_at"),
                    updated_at=edge.get("updated_at"),
                    properties=edge.get("properties", {}),
                )
            logger.info(f"Loaded graph memory with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
        except Exception as e:
            logger.error(f"Failed to load graph memory: {e}")

    def save(self) -> None:
        """Persist graph memory to disk."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            nodes_data = {node: self.graph.nodes[node] for node in self.graph.nodes}
            edges_data = []

            for u, v, key, data in self.graph.edges(keys=True, data=True):
                edges_data.append({
                    "source": u,
                    "target": v,
                    "key": key,
                    "relation": data.get("relation"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "properties": data.get("properties", {}),
                })

            with self.db_path.open("w", encoding="utf-8") as f:
                json.dump({"nodes": nodes_data, "edges": edges_data}, f, indent=2)
            logger.debug("Saved graph memory successfully.")
        except Exception as e:
            logger.error(f"Failed to save graph memory: {e}")

    def add_entity(self, name: str, entity_type: str, properties: dict[str, Any] | None = None) -> str:
        """Add or update an entity in the graph."""
        node_id = name.lower().replace(" ", "_")
        now = datetime.now(UTC).isoformat()

        if self.graph.has_node(node_id):
            # Update existing node properties and history
            existing = self.graph.nodes[node_id]
            history = existing.get("history", [])

            # Track temporal property changes if they differ
            new_properties = properties or {}
            old_properties = existing.get("properties", {})
            changed = {}
            for k, v in new_properties.items():
                if old_properties.get(k) != v:
                    changed[k] = {"old": old_properties.get(k), "new": v, "timestamp": now}

            if changed:
                history.append({"changes": changed, "timestamp": now})

            # Merge properties
            merged_props = {**old_properties, **new_properties}
            self.graph.add_node(
                node_id,
                name=name,
                type=entity_type,
                properties=merged_props,
                created_at=existing.get("created_at", now),
                updated_at=now,
                history=history,
            )
        else:
            # Create new node
            self.graph.add_node(
                node_id,
                name=name,
                type=entity_type,
                properties=properties or {},
                created_at=now,
                updated_at=now,
                history=[],
            )

        self.save()
        return node_id

    def add_relationship(
        self,
        source_name: str,
        target_name: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a temporal relationship between two entities."""
        source_id = source_name.lower().replace(" ", "_")
        target_id = target_name.lower().replace(" ", "_")

        # Ensure nodes exist
        if not self.graph.has_node(source_id):
            self.add_entity(source_name, "Concept")
        if not self.graph.has_node(target_id):
            self.add_entity(target_name, "Concept")

        now = datetime.now(UTC).isoformat()

        # Check if the relation already exists
        exists = False
        for _, _, data in self.graph.edges([source_id], data=True):
            if data.get("relation") == relation:
                # Update relation metadata
                data["updated_at"] = now
                if properties:
                    data["properties"] = {**data.get("properties", {}), **properties}
                exists = True
                break

        if not exists:
            self.graph.add_edge(
                source_id,
                target_id,
                relation=relation,
                created_at=now,
                updated_at=now,
                properties=properties or {},
            )

        self.save()

    def get_entity(self, name: str) -> dict[str, Any] | None:
        """Retrieve entity info and its direct relationships."""
        node_id = name.lower().replace(" ", "_")
        if not self.graph.has_node(node_id):
            return None

        node_data = dict(self.graph.nodes[node_id])
        relationships = []

        # Outgoing relationships
        for _, target, data in self.graph.out_edges(node_id, data=True):
            relationships.append({
                "type": "outgoing",
                "relation": data.get("relation"),
                "target": target,
                "properties": data.get("properties"),
            })

        # Incoming relationships
        for source, _, data in self.graph.in_edges(node_id, data=True):
            relationships.append({
                "type": "incoming",
                "relation": data.get("relation"),
                "source": source,
                "properties": data.get("properties"),
            })

        node_data["relationships"] = relationships
        return node_data

    def query_path(self, start_name: str, end_name: str) -> list[str] | None:
        """Find the shortest path of relationships between two entities (multi-hop)."""
        start_id = start_name.lower().replace(" ", "_")
        end_id = end_name.lower().replace(" ", "_")

        if not self.graph.has_node(start_id) or not self.graph.has_node(end_id):
            return None

        try:
            # Find path using networkx shortest path
            path = nx.shortest_path(self.graph, source=start_id, target=end_id)
            return [self.graph.nodes[node].get("name", node) for node in path]
        except nx.NetworkXNoPath:
            return None

    def get_temporal_history(self, name: str) -> list[dict[str, Any]] | None:
        """Retrieve history of property updates for a specific entity."""
        node_id = name.lower().replace(" ", "_")
        if not self.graph.has_node(node_id):
            return None
        return self.graph.nodes[node_id].get("history", [])
