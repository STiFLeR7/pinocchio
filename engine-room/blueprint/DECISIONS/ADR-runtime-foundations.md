# ADR-013: Nexus Runtime Architectural Foundations & Primitives

Date: 2026-06-19
Status: Closed — Approved

---

## Context

To implement Phase 1 (Core Infrastructure) and Phase 2 (Task Management) without repeating the structural fragility of common agent frameworks, we conducted a deep-dive analysis of the runtime primitives, event state loops, context compiling, and recovery models of **Pi Core**. This record establishes the core primitives and constraints that govern the **Nexus Runtime Engine**.

---

## Decisions

We establish the following runtime design principles:

### 1. Primitive Definitions (Durable vs. Derived)
- **Task (`TaskRecord`)**: The root state primitive.
- **ExecutionStep (`ExecutionRecord`)**: An atomic subprocess invocation block.
- **ExecutionResult (`ExecutionRecord` data)**: The finalized output (logs, stdout/stderr, and JSON metadata).
- **StateTransition (`AuditLogRecord`)**: An immutable, append-only record tracking all lifecycle shifts.
- **Checkpoint (`WorkflowCheckpointRecord`)**: A serialized state snapshot.
- **ContextFrame (Derived)**: The active compiled context window compiled right before LLM invocation.

### 2. Context Compile-Time Decoupling
- Internal Pydantic schemas in `schemas.py` are strictly decoupled from external client models. 
- Decoupled mapper functions format internal database structures into the OpenRouter message schemas right at the network boundary.

### 3. Subprocess Execution Guarding
- **Preflight Guards**: Before any runner execution begins, validation checks against the `ApprovalRecord` database table verify that the execution is authorized.
- **Idempotency Metadata**: Subprocesses must declare an `idempotent` boolean. Automatic retries on crash are blocked if `idempotent = False`.

### 4. Recovery & Observer Sweepers
- We will not rely on in-memory loops to recover from system crashes.
- Heartbeat sweepers (integrated via APScheduler) inspect active `ExecutionRecord` tables. If `last_heartbeat` misses the threshold, the step is marked as failed (`ExitStatus = TIMEOUT`), and a state transition is logged.

---

## Justification

1. **Decoupled Payload Translation**: Decoupling prevents external API updates (e.g. OpenRouter API contract changes) from forcing changes onto our core SQLite schemas.
2. **Immutable Audit Trails**: Relational columns enable fast querying, while `AuditLogRecord` logs are kept strictly append-only, providing perfect observability.
3. **Robust Subprocess Recovery**: Subprocess command executions run outside the Python runtime. Heartbeat sweepers verify execution boundaries, ensuring that crashed or hung subprocesses do not block the task engines indefinitely.
4. **Context Window Protection**: Compacting token lists and writing summary check-points to `WorkflowCheckpointRecord` prevents LLM context collapse in long development sessions.
