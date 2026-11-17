# ADR 0007: Durable Runs, Idempotency, and Side-Effect Safety State Machine

## Status
Accepted

## Context
Production agentic workflows execute multi-step operations that interact with file systems, APIs, messaging channels, and human approval gates. Process crashes, container restarts, or unhandled exceptions during execution risk:
1. **Duplicate External Side Effects**: Blindly retrying failed runs from the beginning re-executes mutating operations (e.g., duplicated file modifications, duplicate payments, re-sent notification blasts).
2. **Lost Approval State**: In-flight Human-in-the-Loop (HITL) approval tickets stored only in volatile memory are wiped on server restart, leaving the agent stranded.
3. **Hidden Ambiguous Completions**: Network dropouts during remote tool invocation leave the system unable to know if the remote service received the mutation. Naive automated retries violate idempotency.

Reference frameworks (LangGraph checkpointing, PydanticAI Temporal activities, CrewAI persisted flows) highlight the requirement for explicit run durability and side-effect contracts.

## Decision
We implement a formal ACID-backed execution coordinator and state machine (`DurableExecutionCoordinator` and `DurableRunStore`):

1. **State Machine Partitioning**:
   - Runs transition through strict states: `PENDING` -> `RUNNING` -> `WAITING_FOR_APPROVAL` -> `COMPLETED` / `FAILED` / `AMBIGUOUS` / `COMPENSATING` / `COMPENSATED`.
   - Each step transitions through: `PENDING` -> `IN_FLIGHT` -> `COMPLETED` / `FAILED` / `AMBIGUOUS` / `SKIPPED` / `COMPENSATED`.

2. **Deterministic Idempotency Deduplication**:
   - Every step computes a deterministic digest: `idemp_<sha256(run_id:step_index:action_type:json(args))[:24]>`.
   - Before executing any action, the coordinator checks if the idempotency key already reached `COMPLETED`. If so, the cached result is returned immediately without re-executing the external action.

3. **Crash Point Recovery & Ambiguity Surfacing**:
   - If a crash occurs while a side-effect action was `IN_FLIGHT`, recovery flags the step as `AMBIGUOUS`. The operator is visibly alerted to the ambiguous boundary rather than executing a duplicate side effect.
   - Non-side-effect steps (e.g., deterministic queries, data transformations) are safely re-run from the exact interrupted index.

4. **Approval Persistence Across Restarts**:
   - When a tool requires human authorization, the step records `approval_ticket_id` and the run enters `WAITING_FOR_APPROVAL`.
   - Following process termination and restart, the coordinator recovers the ticket and awaits human resolution without restarting the run.

5. **SAGA Compensation Chains**:
   - Mutating side-effect steps can register compensation actions (`compensation_action`, `compensation_args`).
   - If a workflow must be aborted, `compensate_run` triggers compensation actions in reverse order of completion.

## Consequences
- Every execution step is recorded in tenant-partitioned SQLite storage (`data/tenants/{tenant_id}/runs.db`).
- 100 crash-point failure injection tests prove zero duplicate external actions.
- Ambient remote ambiguity is explicitly surfaced in machine-readable recovery reports.
- Storage overhead is bounded and partitioned per tenant.
