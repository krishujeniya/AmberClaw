# ADR-0005: Unified Canonical Agent Runtime Routing Across Entry Points

Date: 8 November 2026
Status: accepted for CL-004 unified runtime implementation

## Context and Problem Statement
Observation A03 and CL-004 identified that AmberClaw provided multiple fragmented execution entry paths:
1. `src/amberclaw/agent/loop.py` (`AgentLoop.process_direct`) enforced the complete zero-trust runtime pipeline: tool discovery, Landlock/seccomp sandboxes, memory persistence, human-in-the-loop tickets, and SHA-256 hash-chained audit logging.
2. `src/amberclaw/web/server.py` (`_chat_chunks`) accepted a bound `ChatRuntime` protocol and delegated to `process_direct`.
3. `src/amberclaw/api/v1/chat.py` previously made direct calls to `LLMRouter.generate()`, bypassing agent tools, sandbox isolation, session persistence, and audit logging.

Describing unverified direct model completion as full agent execution creates security, governance, and behavioral discrepancies between the CLI/dashboard and HTTP/SSE API clients.

## Decision
1. **Unified ChatRuntime Protocol**: `ChatService` and `web.server` share the canonical `ChatRuntime` contract (`process_direct(content, *, session_key, channel, chat_id, on_token)`).
2. **Canonical Dispatch Priority**: When an agent runtime is bound to `ChatService`, all API chat requests (`/api/v1/chat` and `/api/v1/chat/stream`) route directly through `runtime.process_direct()`.
3. **Deterministic Token Streaming**: Streaming responses use an asynchronous event queue receiving chunk callbacks from `on_token`, formatting tokens into SSE `token_frame` events and closing with `done_frame`.
4. **Explicit Completion Semantics**: Callers requesting completion-only mode may supply `raw_completion: true`, or fall back to `LLMRouter` only when an agent runtime is not explicitly bound, preventing silent security boundary bypass.

## Consequences
- Single point of governance: CLI, Web Dashboard, Channel Transports, and REST/SSE API endpoints execute with the exact same sandbox policies, memory isolation, and audit receipts.
- Transparent observability: All user-originated actions yield structured JSONL audit entries with attributable session keys (`cli:direct`, `web:<conversation_id>`, `api:<agent_id>`).
- API compatibility is fully preserved while enabling full agent capabilities over standard REST/SSE.
