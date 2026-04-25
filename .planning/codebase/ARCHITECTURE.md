# Architecture

## Core Design Philosophy
AmberClaw uses a **Decoupled Asynchronous architecture** where the "Transport" (Channels) is separated from the "Logic" (Agent Core) by a high-level `MessageBus`.

## System Layers
1. **CLI/Entry Layer**: `amberclaw.cli.commands` — Typer app handling commands like `chat`, `start`, `council`.
2. **Channel Layer**: `amberclaw.channels.*` — Adapters for Slack, Telegram, etc., that publish/subscribe to events.
3. **Bus Layer**: `amberclaw.bus.queue` — `MessageBus` with inbound/outbound queues.
4. **Agent Layer**: `amberclaw.agent.loop` — The `AgentLoop` orchestrates message processing, memory retrieval, and tool calling.
5. **Tool Layer**: `amberclaw.agent.tools.*` — Pydantic-based plugin tools (Registry pattern).
6. **Provider Layer**: `amberclaw.providers.*` — Abstracted LLM clients (LiteLLM-centric).

## Data Flow
1. User message arrives at a `Channel`.
2. Channel publishes `InboundMessage` to `MessageBus`.
3. `AgentLoop` (running in a background task) consumes the message.
4. Agent builds `Context` (History + Memory + Files).
5. Agent calls LLM iteratively, executing `Tools` as needed.
6. Agent publishes `OutboundMessage` to `MessageBus`.
7. Channel consumes the response and sends it back to the user.

## Key Abstractions
- `PydanticTool`: Self-describing tool definition with auto-generation of OpenAI schemas.
- `ContextBuilder`: Centralized logic for gathering all relevant info for a prompt.
- `LLMProvider`: Unified interface for multiple LLM backends.
