"""Credentialless persistence and optional graph regressions."""

from pathlib import Path

import pytest

from amberclaw.memory import graph_memory, manager, memory_manager


def test_optional_retrieval_failure_preserves_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise ValueError("OPENAI_API_KEY is required")

    monkeypatch.setattr(manager, "HybridRetriever", unavailable)
    memory = manager.MemoryManager(tmp_path, recall_mode="context")
    assert memory.hybrid_retriever is None
    memory.close()


def test_mem0_graph_persists_entities_when_extraction_sdk_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(memory_manager, "Memory", None)
    manager = memory_manager.MemoryManager(tmp_path)
    assert manager._graph is not None
    manager._graph.add_entity("Amber", "Project")
    reloaded = graph_memory.TemporalGraphMemory(
        tmp_path / "mem0_db" / "graph_memory.json"
    )
    assert reloaded.get_entity("Amber") is not None


async def test_credentialless_context_persists_and_recalls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    memory = manager.MemoryManager(tmp_path, recall_mode="context")
    try:
        await memory.add_turn("offline", "user", "local context survives")
        recalled = await memory.recall("unused", "offline")
        assert recalled[0]["content"] == "local context survives"
    finally:
        memory.close()
