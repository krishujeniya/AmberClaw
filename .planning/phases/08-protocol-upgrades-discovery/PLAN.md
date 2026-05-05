# Phase 8 Plan: Protocol Upgrades & Discovery

## Objective
Upgrade AmberClaw's communication capabilities to the 2026 standards, ensuring interoperability with the latest MCP spec and enabling inter-agent collaboration via A2A with ZeroConf discovery.

## Tasks

### 1. Upgrade MCP to 2026 Spec (AC-093)
- [ ] **Sampling Support**:
    - Implement `session.set_sampling_handler` in `amberclaw/agent/tools/mcp.py`.
    - Map MCP sampling requests to `provider.chat_with_retry`.
    - Allow tools to request LLM completions for sub-tasks.
- [ ] **SSE Transport Hardening**:
    - Ensure `httpx` client factory in `mcp.py` handles authentication and timeouts for long-running streaming results.
- [ ] **Prompt Templates**:
    - Register MCP Prompts as native AmberClaw prompt templates if available.

### 2. Implement A2A Protocol Support (AC-094)
- [ ] **A2A Server (FastAPI)**:
    - Add `fastapi` and `uvicorn` to `pyproject.toml`.
    - Create `amberclaw/api/app.py` with standard A2A JSON-RPC 2.0 handlers.
    - Expose `GET /.well-known/agent-card.json` returning the manifest from `loop.a2a_manager`.
- [ ] **A2A Task Management**:
    - Extend `A2AManager` in `a2a.py` to support task status tracking (`in-progress`, `completed`).
    - Use Server-Sent Events (SSE) for real-time task progress updates.

### 3. MCP Discovery & Dynamic Registration (AC-095)
- [ ] **mDNS (ZeroConf) Integration**:
    - Add `zeroconf` to `pyproject.toml`.
    - Implement a background scanner in `_mcp_discovery_loop` to detect `_mcp._tcp` and `_a2a._tcp` services.
- [ ] **Hot-Swapping**:
    - Update `ToolRegistry` to allow thread-safe dynamic registration.
    - Ensure `AgentGraph` can pick up new tools without a full restart (re-initialization of tool node).

## Architecture Details
- **API Server**: Hosted on `localhost:8000` (configurable), providing the ingress for other agents.
- **Agent Card**: Advertises capabilities (`rag`, `web`, `data`, `mcp`) and the A2A endpoint.
- **Discovery**: Agents advertise themselves via mDNS when the gateway starts.

## Verification
- [ ] `mcp` library version is >= 1.27.0.
- [ ] `Sampling` works: An MCP tool can successfully request a text completion from the agent.
- [ ] `Agent Card` is accessible via HTTP.
- [ ] `A2A` messaging: Successful request/response between two local AmberClaw instances.
- [ ] `mDNS`: A new MCP server on the network is automatically registered as a tool.
