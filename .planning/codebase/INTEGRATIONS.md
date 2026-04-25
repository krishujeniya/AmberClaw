# Integrations

## LLM Providers
AmberClaw leverages LiteLLM to support the vast majority of AI models:
- **Direct**: OpenAI, Anthropic, Gemini, DeepSeek, Groq, Cohere.
- **Gateways**: OpenRouter, AiHubMix, SiliconFlow, VolcEngine.
- **Local**: Ollama, vLLM.
- **Enterprise**: Azure OpenAI, Google Cloud Vertex AI (via litellm).

## Interaction Channels
Unified messaging support via `MessageBus`:
- **Slack**: Socket mode support.
- **Telegram**: Bot API.
- **Discord**: Gateway API.
- **WhatsApp**: WebSocket bridge.
- **Email**: IMAP/SMTP integration.
- **Enterprise**: Feishu/Lark, DingTalk, QQ.

## External Tools
- **Search**: Brave Search API (via `WebSearchTool`).
- **Cloud**: Google Drive (via `DriveTool`).
- **MCP**: Model Context Protocol servers for standard tool extensions.
- **Data**: CSV/Excel/SQLite support via DataAgent.

## Storage & Memory
- **Local Filesystem**: Primary workspace storage.
- **Memory**: JSON-based `MemoryStore` for conversation context.
- **RAG**: Local JSON knowledge store (Personal RAG).
