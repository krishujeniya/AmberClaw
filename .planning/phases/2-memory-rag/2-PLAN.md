---
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - amberclaw/agent/tools/personal_assistant.py
  - amberclaw/memory/memory_manager.py
  - amberclaw/memory/rag_pipeline.py
  - amberclaw/memory/graph_memory.py
  - amberclaw/memory/__init__.py
autonomous: true
---

# Phase 2: Memory, Knowledge & RAG Systems Upgrade

## Goal
Implement a robust memory and RAG architecture for AmberClaw, supporting Mem0 v1.0+, temporal knowledge graphs, vector DB backends, hybrid retrieval, and automated fact extraction.

## Tasks

<task>
<id>1</id>
<title>Upgrade Mem0 and Implement Vector DB Support</title>
<description>
Update `pyproject.toml` to require `mem0ai>=1.0.0` and add vector database dependencies (chromadb, lancedb, qdrant-client). Create a `memory_manager.py` that abstracts Mem0 initialization, making cross-session persistent memory the default, and supporting multi-scope scoping (user_id, agent_id, session_id).
</description>
<read_first>
- pyproject.toml
- amberclaw/agent/tools/personal_assistant.py
</read_first>
<action>
1. Edit `pyproject.toml` to bump `mem0ai>=1.0.0` in the `memory` extra.
2. Create `amberclaw/memory/memory_manager.py` with a `MemoryManager` class that initializes Mem0 with persistent vector DB (Chroma by default) and supports multi-scope parameters.
3. Update `AssistantTool` in `personal_assistant.py` to use `MemoryManager` instead of raw Mem0.
</action>
<acceptance_criteria>
- `pyproject.toml` contains `mem0ai>=1.0.0`
- `amberclaw/memory/memory_manager.py` contains `class MemoryManager`
- `AssistantTool` uses the new `MemoryManager`
</acceptance_criteria>
</task>

<task>
<id>2</id>
<title>Build RAG / Document Knowledge Base Pipeline</title>
<description>
Implement a robust RAG pipeline with hybrid retrieval (Vector + BM25 Keyword + Rerank) and multi-source document ingestion (PDF, markdown, DOCX).
</description>
<read_first>
- amberclaw/memory/memory_manager.py
</read_first>
<action>
1. Create `amberclaw/memory/rag_pipeline.py`.
2. Implement `DocumentIngestor` using `unstructured` for multiple file formats.
3. Implement `HybridRetriever` using LangChain's vector stores, BM25Retriever, and ContextualCompressionRetriever (Reranker).
4. Add CLI command stub or tool for `amberclaw ingest <path>`.
</action>
<acceptance_criteria>
- `rag_pipeline.py` contains `DocumentIngestor` and `HybridRetriever` classes.
- HybridRetriever implements both dense and keyword search.
</acceptance_criteria>
</task>

<task>
<id>3</id>
<title>Knowledge Graph and Temporal Memory</title>
<description>
Integrate graph memory construction and temporal fact tracking. Extract institutional knowledge and store it with validity periods.
</description>
<read_first>
- amberclaw/memory/memory_manager.py
</read_first>
<action>
1. Create `amberclaw/memory/graph_memory.py`.
2. Implement Graph extraction using Mem0's graph capabilities or a custom NetworkX/Neo4j implementation.
3. Add temporal tagging to extracted facts so queries respect past vs. present states.
4. Integrate fact extraction pipeline into `MemoryManager.add()`.
</action>
<acceptance_criteria>
- `graph_memory.py` contains logic for graph relationship extraction.
- Memory entries store temporal metadata.
</acceptance_criteria>
</task>

<task>
<id>4</id>
<title>RAGAS-Based Evaluation Script</title>
<description>
Add an evaluation script using RAGAS metrics to measure RAG quality.
</description>
<read_first>
- pyproject.toml
</read_first>
<action>
1. Add `ragas` to `dev` dependencies in `pyproject.toml`.
2. Create `scripts/eval_rag.py` that implements a basic evaluation using RAGAS for faithfulness and answer relevancy.
</action>
<acceptance_criteria>
- `scripts/eval_rag.py` exists and imports `ragas`.
- `pyproject.toml` contains `ragas` dependency.
</acceptance_criteria>
</task>

## Verification
- Run `npm run typecheck` or equivalent Python static analysis (mypy/pyright) to ensure strict typing.
- Ensure all tests pass.
