# Longitudinal Memory Retention and Deletion Propagation Specification

- **Milestone:** CL-013
- **Commit:** `9ece8c02f4ce31178bed489ca07f26af29d6d735`
- **Scope:** Relational SessionDB, Vector Retrieval Index, Temporal Graph Memory

---

## 1. Multi-Store Architecture Overview

AmberClaw memory spans three synchronized tiers:
1. **Relational Session Store (`SessionDB`):** Tracks chat turns, role definitions, token counts, and session metadata.
2. **Vector Index (`ChromaDB` / dense embedding store):** Indexes episodic and document semantic chunks tagged by `tenant_id` and `session_id`.
3. **Temporal Knowledge Graph (`TemporalGraphMemory`):** Captures structured entities, node properties, directional relationships, and timestamped assertion intervals `[valid_from, valid_to]`.

---

## 2. Retention Limits & TTL Policies

| Store | Default Retention / TTL | Maximum Allowed TTL | Purge Mechanism |
|---|---|---|---|
| **Session Turns** | 90 days from last activity | 365 days (configurable) | Automated scheduled vacuum / explicit API deletion |
| **Vector Chunks** | Linked to parent session / document lifespan | 365 days | Synchronous cascade delete on parent entity removal |
| **Graph Entities & Edges** | Indefinite until superseded or explicitly purged | Policy-defined | Explicit deletion or tombstone supersession |
| **Audit Logs** | Immutable 365-day retention with external HMAC anchors | Indefinite | WORM storage policy |

---

## 3. Deletion Propagation Guarantees (GDPR Article 17)

When a deletion request (`DELETE /api/v1/memory/sessions/{id}` or `DELETE /api/v1/memory/purge`) is executed:
1. **Relational Wipe:** All records matching `session_id` and caller `tenant_id` are removed from the database within an ACID transaction.
2. **Vector Wipe:** Embeddings matching the tenant and session keys are deleted from the vector collection.
3. **Graph Memory Wipe:** Entities and all connected incoming and outgoing relationship edges are purged via `delete_entity` and `delete_relationship`.
4. **Zero Orphan Invariant:** A deletion receipt is generated, confirming 0 residual records across all three stores.

---

## 4. Temporal Contradiction Resolution & Provenance

- **Temporal Supersession:** When a newly ingested fact contradicts an existing graph relationship, the earlier assertion is closed (`valid_to = current_timestamp`) and the new relationship is recorded.
- **Grounding Citations:** Answers generated from memory must cite exact `chunk_id` and character span offsets `[start, end]` from verified source documents.
- **Strict Abstention:** When evidence is missing, conflicting without temporal resolution, or below the 0.70 confidence threshold, the runtime abstains with explicit error codes (`INSUFFICIENT_EVIDENCE`, `UNSUPPORTED_QUERY`, `POISONING_DETECTED`).

---

## 5. Security & Isolation Boundaries

- **Cross-Tenant Isolation:** Retrieval queries strictly partition by `tenant_id`. Cross-tenant retrieval queries return zero candidate matches.
- **Adversarial Injection Defense:** Memory ingestion sanitizes prompt injection indicators (e.g. system instructions override, ignore previous instructions, canary exfiltration). Detected injections trigger immediate abstention and security audit logging.
- **Export Portability (GDPR Article 20):** Export payloads contain schema versioning, message history, token accounting, and a verifiable SHA-256 digest over the canonical JSON payload.
