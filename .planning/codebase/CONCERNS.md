# Concerns

## Technical Debt
- **DataAgent Redundancy**: `amberclaw.data` contains many legacy `VibeDS` stubs (TODO items in `orchestration.py`, `pipeline.py`). Needs consolidation into the unified toolset.
- **Personal Assistant**: Currently uses a simplified workspace history. Needs more robust memory compression/summarization.
- **RAG**: The Knowledge RAG (`personal_rag.py`) is basic substring search. Needs vector embedding support.

## Performance
- **Blocking I/O**: Some data science operations (Pandas) may block the event loop. Need to offload to threads.
- **Context Bloat**: Long-running conversations accumulate history fast. Context management (compaction) is a priority.

## Security
- **Shell Exec**: `ExecTool` runs commands in the host shell. Needs stronger sandboxing or strict safety filters.
- **Workspace Restriction**: Configurable but needs rigorous verification across all tools (Write/Edit/Read).

## Architecture Upgrades Needed
- **MCP Migration**: Fully adopt MCP for all external tools to reduce internal code complexity.
- **LiteLLM Observability**: Integrate tracing and cost tracking natively.
- **Parallel Tool Use**: Optimize `AgentLoop` to execute multiple tool calls concurrently.
