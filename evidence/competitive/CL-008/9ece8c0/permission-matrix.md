# AmberClaw Endpoint-to-Store Multi-Tenant Permission Matrix

## Executive Summary
This document defines the authoritative access control matrix and partition boundaries across all AmberClaw HTTP endpoints, background worker tasks, state stores, and tool dispatchers.

Tenant isolation is enforced through:
1. **Cryptographic Identity Claims**: Access and refresh tokens carry immutable `tenant_id` claims verified via HS256 HMAC signatures.
2. **Context Propagation**: Authenticated requests bind `TenantContext` via `contextvars.ContextVar`, scoping all storage transactions to `data/tenants/{tenant_id}/`.
3. **Escalation Denial**: Any caller-supplied tenant identifier (such as `X-Tenant-ID` header, `tenant_id` or `org_id` parameters) differing from the token's authenticated tenant is rejected with `HTTP 403 Forbidden` unless the caller possesses verified `admin` role.
4. **Physical Database and File Separation**: SQLite databases and JSON stores are physically stored in dedicated directory trees per tenant.
5. **Tool Execution RBAC**: Tools check permissions against `SecurityConfig.rbac` prior to dispatch; unauthorized roles raise `RBACPermissionDenied`.

---

## Endpoint-to-Store Matrix

| Endpoint | Method | Underlying Store | Tenant Isolation Guarantee | Escalation Denial Behavior |
|---|---|---|---|---|
| `/api/v1/agents/spawn` | POST | `data/tenants/{tenant_id}/agents.json` | Scoped to caller tenant via `TenantContext`. | Cannot spawn agent into external tenant. |
| `/api/v1/agents` | GET | `data/tenants/{tenant_id}/agents.json` | Lists only active tenant's agents. | Cross-tenant listing returns 403 or empty. |
| `/api/v1/agents/{id}/chat` | POST | `data/tenants/{tenant_id}/agents.json` | Resolves agent exclusively in caller partition. | Returns 404 if agent exists only in another tenant. |
| `/api/v1/chat` | POST | `data/tenants/{tenant_id}/agents.json` | Agent lookup and memory scoped to caller tenant. | Unauthenticated or foreign agent returns 404. |
| `/api/v1/chat/stream` | POST | `data/tenants/{tenant_id}/agents.json` | SSE stream scoped to caller tenant. | Unauthenticated or foreign agent returns 404. |
| `/api/v1/memory/export` | GET | `data/tenants/{tenant_id}/sessions.db` | GDPR export strictly bounded to tenant database. | Specifying foreign `org_id` returns 403 Forbidden. |
| `/api/v1/memory/sessions/{id}/turns` | GET | `data/tenants/{tenant_id}/sessions.db` | Reads exclusively from caller's SQLite partition. | Foreign session ID returns 0 turns. |
| `/api/v1/memory/sessions/{id}` | DELETE | `data/tenants/{tenant_id}/sessions.db` | Deletes only within caller's partition. | Cannot delete foreign tenant turns. |
| `/api/v1/memory/purge` | DELETE | `data/tenants/{tenant_id}/sessions.db` | Purges only caller tenant partition. | Leaves all other tenant databases intact. |
| `/api/v1/auth/token/revoke` | POST | `TokenRevocationStore` | In-memory singleton with immediate cross-thread sync. | Revoked JTI or session rejects subsequent calls with 401. |
| `ToolRegistry.execute` | Method | Process Sandbox / Execution Environment | Enforces `check_tool_permission` using active sender context. | Unauthorized roles raise `RBACPermissionDenied` before tool execution. |

---

## Verification Evidence
All matrix assertions were verified deterministically via `tests/unit/api/test_tenant_isolation_e2e.py`:
- Cross-tenant agent isolation: PASS
- Caller-supplied tenant escalation denial: PASS
- Cross-tenant memory and GDPR isolation: PASS
- Immediate session revocation: PASS
- Unauthorized tool dispatch denial: PASS
- Concurrent worker multi-tenant separation: PASS
