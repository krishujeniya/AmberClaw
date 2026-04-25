# AmberClaw Bug Report — Status: RESOLVED (April 25, 2026)

## ✅ Stabilization Overview
The codebase has undergone a comprehensive stabilization sweep. All critical runtime failures, connection leaks, and type consistency issues identified in previous audits have been resolved. The project now passes `pyright` and `ruff` checks and all core unit tests.

## 🛠️ Resolved Issues

### 1. Unified MCP Tool Logic (`mcp.py`)
- **Fixed**: Removed hypothetical `get_task_status` method calls and unified polling logic within the `AsyncExitStack` context.
- **Improved**: Added defensive `mcp.types` imports to handle SDK variability.

### 2. Type-Safe Tool Wrappers (`base.py`)
- **Fixed**: Resolved inheritance-based metadata access in `WrappedTool`. Correctly handles `args_schema` access for `PydanticTool` subclasses while remaining safe for plain `Tool` instances.
- **Fixed**: `_validate` logic now properly checks types before calling length-dependent methods.

### 3. Agent Initialization Consistency (`loop.py`)
- **Fixed**: Ensured `embedding_model` consistency across `KnowledgeSearchTool` and `KnowledgeAddTool`.
- **Fixed**: Aligned `lc_model` and `embedding_model` assignments to match expected constructor types.

### 4. Memory & RAG Reliability (`personal_assistant.py`, `personal_rag.py`)
- **Fixed**: Corrected result indexing for Mem0 search results.
- **Fixed**: Added robust response parsing for LiteLLM embeddings, handling both dict and object return types.
- **Added**: 1536-dim zero-vector fallbacks for dimension-safe embedding operations.

### 5. SQL Connection & Engine Disposal (`data_sql.py`, `agent_templates.py`)
- **Fixed**: Added mandatory `try-finally` blocks to ensure SQL connections are closed and engines are disposed after use.
- **Fixed**: Improved `BaseAgent` template connection management.

### 6. Asynchronous Execution Safety
- **Fixed**: All synchronous agent `invoke_agent` calls in Data tools are now correctly offloaded to `asyncio.to_thread`.
- **Files**: `data_clean.py`, `data_viz.py`, `data_eda.py`, `data_sql.py`.

## 📈 Current Status
- **Static Analysis**: `pyright` (AmberClaw core): 0 Errors.
- **Linting**: `ruff` check: 0 Errors.
- **Testing**: `pytest` (Tool suite): 28/28 Passed.
- **Deployment**: Successfully pushed to `krishujeniya/AmberClaw` with passing CI/CD.
