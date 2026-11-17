# CL-020: Protocol Compatibility and Dependency License Review

## 1. Protocol Compatibility Matrix

| Protocol / Standard | Version | Support Level | Implementation Location | Verification Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Model Context Protocol (MCP)** | 2024-11-05 | Full Native Client | `src/amberclaw/agent/tools/mcp.py` | Discovers tools via `.well-known/mcp.json`, wraps tool schemas into Pydantic models. |
| **MCP Task Extensions** | 2026.1 | Full Native Client | `src/amberclaw/agent/tools/mcp.py` | Detects `supports_tasks` and routes long-running calls to `create_task`. |
| **Agent-to-Agent (A2A)** | 1.0.0 | Full Native Protocol | `src/amberclaw/api/stream/protocol.py` | Typed streaming envelope with JSON-RPC semantics and message sequencing. |
| **LangGraph State Graph Migration** | 0.2.x | Selective Migration | `src/amberclaw/agent/contracts/migration_adapter.py` | Imports tool, transform, and approval nodes; quarantines dynamic evaluation nodes. |
| **Pydantic Model Contracts** | Pydantic v2 | Full Schema Ratchet | `src/amberclaw/agent/contracts/tool_contracts.py` | Strict validation of input and output schemas with typed exceptions. |

## 2. Security and Authorization Invariants
- **Scope Preservation**: All imported workflow steps must declare their required authorization scopes explicitly. Calls without verified tokens containing required scopes raise `InsufficientScopeError`.
- **Malformed Output Containment**: Tool execution results that do not strictly conform to the output contract schema raise `MalformedToolOutputError`. Raw exception traces and internal memory buffers are suppressed to prevent data leakage.
- **Node Quarantine**: Any imported graph node containing arbitrary runtime evaluation (such as untyped `eval()`, subprocess invocation, or unbounded cycles) is marked as unsupported and rejected from execution prior to workflow initiation.

## 3. Dependency License Audit
A review of project dependencies confirms that all imported third-party libraries use permissive open-source licenses:

| Package | Declared License | Permissibility Status |
| :--- | :--- | :--- |
| `pydantic` / `pydantic-core` | MIT | Permissible (no copyleft obligations) |
| `fastapi` / `starlette` | MIT | Permissible |
| `sqlalchemy` / `alembic` | MIT | Permissible |
| `httpx` / `httpcore` | BSD-3-Clause | Permissible |
| `loguru` | MIT | Permissible |
| `typer` / `rich` | MIT | Permissible |
| `langgraph` (selective adapter) | MIT | Permissible |

Zero dependencies contain GPL, AGPL, SSPL, or commercial proprietary restrictions that would impede private on-premises deployment.
