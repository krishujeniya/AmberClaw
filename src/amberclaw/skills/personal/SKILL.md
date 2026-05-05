---
name: assistant
description: "RAG-augmented AI assistant powered by Google Gemini with MongoDB-backed knowledge base, chat history, and feedback learning."
metadata: {"amberclaw":{"emoji":"🤖","requires":{"env":["GEMINI_API_KEY"],"services":["mongodb"]}}}
---

# Personal Assistant — AI Assistant

RAG-augmented conversational AI integrated into AmberClaw as native tools.

## Tools

### `assistant_chat`

Chat with Personal Assistant using context from conversation history, knowledge base, and feedback.

```
Use the assistant_chat tool to ask questions, get help, or have a conversation.
Personal Assistant remembers previous messages within a session and searches its knowledge base automatically.
```

Parameters:
- `message` (required) — The message to send
- `session_id` (optional) — Session ID for context continuity (defaults to today's date)

### `assistant_knowledge_search`

Search the RAG knowledge base built from Google Drive documents.

```
Use assistant_knowledge_search to find specific facts, documentation, or reference material
from the user's uploaded knowledge base.
```

Parameters:
- `query` (required) — Search query
- `top_k` (optional) — Number of results (1-10, default: 3)

## Configuration

Set in `~/.amberclaw/config.json` under `assistant`:

```json
{
  "assistant": {
    "enabled": true,
    "model": "gemini-2.5-flash",
    "mongodbUri": "mongodb://localhost:27017",
    "googleApiKey": ""
  }
}
```

Environment variables: `GEMINI_API_KEY` or `GOOGLE_API_KEY`, `MONGODB_URI`

## CLI Commands

- `amberclaw assistant telegram` — Start Telegram bot
- `amberclaw assistant sync` — Sync Google Drive → RAG knowledge base
- `amberclaw assistant status` — Check connection status
