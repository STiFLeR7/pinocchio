# ADR-012: Pi Core Systems Patterns Adoption Decisions

Date: 2026-06-19
Status: Closed — Approved

---

## Context

Following the rejection of the Pi framework as a library dependency (ADR-003), this record documents the systems-design and architectural patterns we choose to extract from **Pi Core** and apply to the **Nexus Control Plane**. This ensures that we do not rebuild agentic capabilities from scratch without utilizing proven systems-design reference points.

---

## Decision Matrix

We evaluate and categorize Pi Core's architectural patterns as follows:

| Pattern ID | Pattern Name | Decision | Nexus Implementation Plan |
|---|---|---|---|
| **PAT-001** | Append-Only Event Reduction | **Adapt** | Relational state columns are stored in SQLite (for fast queries), but all state transitions must append an immutable entry to `AuditLogRecord`. |
| **PAT-002** | Decoupled API/Internal Schemas | **Adopt** | Decouple internal task models from OpenRouter payloads. Use translator mapping functions right before OpenRouter requests. |
| **PAT-003** | Pre-Execution Interception | **Adapt** | Execute database-backed validation check (`beforeToolCall`) against `ApprovalRecord` before starting any runner subprocess. |
| **PAT-004** | Sequential Ordering of Parallel Logs | **Adopt** | Run subprocess execution steps concurrently via Python `asyncio`, but log stdout outputs sequentially in the database to maintain context reproducibility. |
| **PAT-005** | Context Compaction | **Adapt** | Track active tokens during turn execution. Summarize conversation logs via OpenRouter and write checkpoints to `WorkflowCheckpointRecord` when context window is 75% full. |
| **PAT-006** | Steering and Follow-up Queues | **Adapt** | Implement a database-backed execution queue where jobs can be steered (paused/aborted) via external owner commands. |

---

## Justification

1. **Append-Only Event Ledger (PAT-001)**: Reconstructing state tree branches from a raw log on every API call (as Pi does) is slow and hard to query inside SQL. By storing current states in relational columns (SQLite indexing) and logging changes to `AuditLogRecord`, we combine fast query performance with an immutable audit trail.
2. **Decoupled API Schemas (PAT-002)**: Eliminates tight coupling between our SQLite memory models and external LLM provider models, allowing the system to update provider integrations without schema migrations.
3. **Validation Gates (PAT-003 & PAT-004)**: Ensures strict governance and safety. No tool execution subprocess can run unless it passes explicit validation checks against active approvals, and order-preservation prevents non-deterministic prompt layouts.
4. **Context Compaction (PAT-005)**: Prevents context collapse in long-running developer sessions, ensuring the orchestrator maintains reasoning quality.

---

## Consequences

- **Phase 1 Architecture**: The Event Gateway and Task Engine will implement strict schema mapping (`PAT-002`) and append-only database audit logs (`PAT-001`).
- **Phase 2 Architecture**: Task lifecycles will support steering state updates (Pause/Cancel) mapped directly onto the database execution queues (`PAT-006`).
- **Phase 3 & 4 Architecture**: Subprocess runners will enforce pre-flight approval gate validations (`PAT-003`) and write concurrent task outputs sequentially (`PAT-004`).
- **Memory Layer**: `WorkflowCheckpointRecord` and `AuditLogRecord` tables are confirmed as our primary state-durability targets.
