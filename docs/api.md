# API Reference & Protocols

The AmberClaw FastAPI Gateway provides programmatic endpoints for agent interactions, streaming responses, memory management, and telemetry.

---

## 🔐 Authentication

All `/api/v1/` routes (except public health checks and login) require authentication via Bearer JWT or API Key:

```http
Authorization: Bearer <your_jwt_token>
```

Or via API key header:

```http
X-API-Key: <your_api_key>
```

---

## 📡 Core Endpoints

### 1. Authentication
- `POST /api/v1/auth/token`: Obtain a JWT access token.
- `GET /api/v1/auth/me`: Inspect the authenticated principal and roles.

### 2. Chat & Inference
- `POST /api/v1/chat`: Synchronous multi-turn chat completion.
  - **Request Body**: `{ "message": "Analyze system load", "model": "gpt-4o" }`
  - **Response**: `{ "reply": "...", "model": "gpt-4o", "usage": { ... } }`
- `POST /api/v1/chat/stream`: Server-Sent Events (SSE) token stream.
  - **Chunk Types**:
    - `event: token` — Individual generated tokens `{ "content": "Hello", "index": 0 }`
    - `event: thought` — Agent scratchpad reasoning
    - `event: tool_call` — Tool invocation details
    - `event: done` — Stream completion `{ "total_tokens": 42, "finish_reason": "stop" }`
    - `event: error` — Error payload `{ "error": "...", "code": "..." }`

### 3. Agent & Session Management
- `GET /api/v1/agents`: List configured agents (paginated with `limit` and `offset`).
- `POST /api/v1/agents`: Create a new custom agent profile.
- `GET /api/v1/agents/{agent_id}`: Retrieve agent details.

### 4. Memory & SessionDB
- `GET /api/v1/memory/sessions`: List active sessions.
- `GET /api/v1/memory/sessions/{id}/turns`: Paginated conversation history with FTS5 search.
- `DELETE /api/v1/memory`: GDPR Right-to-be-Forgotten permanent memory purge.

### 5. Governance & Human-in-the-Loop
- `GET /api/v1/tickets/pending`: List actions awaiting human approval.
- `POST /api/v1/tickets/{id}/approve`: Approve high-risk execution.
- `POST /api/v1/tickets/{id}/reject`: Reject execution request.

### 6. Telemetry & Diagnostics
- `GET /health`: Gateway liveness and readiness probe.
- `GET /metrics`: Prometheus metric exposition (throughput, latency histograms, token usage).
- `GET /api/v1/providers/health`: Real-time status of configured LLM providers.
