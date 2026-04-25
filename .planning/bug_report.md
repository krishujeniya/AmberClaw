# AmberClaw Bug Report — April 25, 2026

## 🔴 Critical Architectural Issues

### 1. `amberclaw/agent/tools/mcp.py` — Runtime Failures
- **Hypothetical Methods**: Line 79 calls `self._session.get_task_status(task_id)` which is documented as "Hypothetical SDK method". This will crash at runtime.
- **Import Errors**: Massive static analysis failures for `mcp` library parts. Likely version mismatch or missing stubs in environment.

### 2. `amberclaw/agent/tools/base.py` — Property Access Errors
- **WrappedTool Regression**: Line 153 tries to access `outer_self.args_schema` but `Tool` base class lacks this attribute. Only `PydanticTool` has it.
- **Type Validation**: `_validate` (Line 240) calls `len()` on `Any` type, causing Pyright errors.

### 3. `amberclaw/agent/loop.py` — Initialization Mismatches
- **Type Compatibility**: `self.embedding_model` is `Optional[str]`, but `KnowledgeSearchTool` and `KnowledgeAddTool` expect `str`.
- **Argument Drift**: Data tools (`DataCleanTool`, etc.) are instantiated with `model` but their `__init__` signatures might not perfectly align with the provider object type.

## 🟡 Tool-Specific Bugs

### 4. `amberclaw/agent/tools/personal_assistant.py`
- **Indexing Error**: Line 161 tries to `get("memory")` from a search result that Pyright identifies as a sequence (list/tuple). Requires proper type narrowing or `getattr` check.

### 5. `amberclaw/agent/tools/drive.py`
- **Dependency Issues**: Import failures for `google-auth` and `google-api-python-client`.
- **Abstract Logic**: Pyright reports missing `run` implementations even though they exist (likely a signature mismatch with `PydanticTool`).

### 6. `amberclaw/agent/tools/personal_rag.py`
- **LiteLLM Rerank**: Excessive use of `getattr` on response objects. Needs explicit type checking or structured parsing.

## 🟢 Environment & Build

### 7. `.gitignore`
- Missing modern Python noise patterns (Hatch, UV artifacts, local `.planning` sub-items).

### 8. `pyproject.toml`
- Dependency list might be missing explicit versions for `mcp` sub-packages if they are split.
