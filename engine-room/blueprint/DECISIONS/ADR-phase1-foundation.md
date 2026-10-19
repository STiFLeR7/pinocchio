# ADR-014: Nexus Phase 1 Foundation & Service Boundaries Approval

Date: 2026-06-19
Status: Approved — Ready for Implementation
Proposed By: Antigravity AI

---

## Context

Before commencing Phase 1 (Core Infrastructure) production coding, we must establish a formal translation of the **Nexus Runtime Architecture** into concrete Python constructs, relational database schemas, event payload models, package boundaries, and execution safety rules. This exercise resolves the structural risks identified during the Pi Core meta-investigation, ensuring that Phase 1 implementation proceeds with clear interface boundaries and zero circular dependencies.

---

## Decisions

We approve and adopt the following technical mapping, schemas, and boundaries:

### 1. Runtime-to-Code Mapping Approval
The eight abstract runtime primitives are translated directly into the following Python constructs:
- **Task**: `TaskRecord` (SQLAlchemy ORM model in `models.py`) and `TaskStatus` (enum in `types.py`). Status changes require a row lock on the task row inside SQLite to ensure serializability.
- **ExecutionStep**: `ExecutionStepRecord` (SQLAlchemy ORM model tracking individual step status and OS pid).
- **ExecutionResult**: Payloads stored directly in `ExecutionRecord` as text-based `logs` (concatenated stdout/stderr streams) and JSON `result` fields.
- **StateTransition**: Immutable append-only `AuditLogRecord` logs tracking all lifecycle changes.
- **Checkpoint**: `WorkflowCheckpointRecord` storing serialized JSON memory snapshots.
- **ContextFrame**: Derived Pydantic schema compiled dynamically at network boundaries.
- **ApprovalStatus**: `ApprovalRecord` managing manual authorization gates.
- **ActiveToolset**: Yaml settings (`config/settings.yaml` and `config/repositories.yaml`) mapped to task configurations.

### 2. Database Schema Design (SQLite WAL Mode)
We approve the following database schema design layout:
- **Write-Ahead Logging (WAL)**: SQLite is set to WAL mode to support concurrent reads while a write transaction is active.
- **Pragmas**: Foreign keys must be enabled on every connection via SQLite event listeners.
- **Table Registry**:
  - `tasks`: Core task tracker.
  - `approvals`: Human-in-the-loop authorization gates with a 24-hour expiration threshold.
  - `executions`: Parent execution record.
  - `execution_steps`: Individual subprocess execution steps with `pid` and `last_heartbeat` columns.
  - `audit_logs`: Immutable, append-only system ledger.
  - `workflow_checkpoints`: Serialized snapshots of workflow states.
  - `research_jobs`: Recurring cron-based jobs managed by the scheduler.
  - `system_events`: Database-backed outbox cache for normalizations.
- **Indexes**: Strict indexing is applied to `correlation_id` columns, entity types/ids, and query fields to prevent performance degradation.

### 3. Event Routing and Payload Contracts
- **Frozen Event Models**: All first-class events (e.g. `TaskCreated`, `ApprovalGranted`, `ExecutionHeartbeat`) are defined as frozen Pydantic schemas inheriting from a base `NexusEvent` envelope.
- **Event Gateway**: An event-routing hub (`nexus/gateway/`) processes system events and routes them to subscribing modules.
- **Trace Correlation**: A unique `correlation_id` (UUID) must be included in all events and propagated to all subsequent database log records to allow cross-system trace reconstruction.

### 4. Service Package Boundaries and Import Constraints
To prevent circular dependencies, we establish a strict layered architecture:
- **Layer 1: core** (`nexus/core/`): Base exceptions, types, enums, settings. (No imports from other layers).
- **Layer 2: events** (`nexus/events/`): Event Gateway, schemas, normalizer. (Imports Layer 1 only).
- **Layer 3: memory** (`nexus/memory/`): SQLAlchemy connection pool, migration schemas, repositories. (Imports Layer 1 & 2).
- **Layer 4: approvals & integrations** (`nexus/approvals/`, `nexus/integrations/`): Governance gates, Discord, Email, and OpenRouter integration clients. (Imports Layers 1-3).
- **Layer 5: execution** (`nexus/execution/`): Subprocess runners, standard stream loggers. (Imports Layers 1-4).
- **Layer 6: scheduler & agents** (`nexus/scheduling/`, `nexus/agents/`): Background schedulers, autonomous agent planning loops. (Imports Layers 1-5).

**Strict Import Rule**: Lower-numbered layers MUST NOT import from higher-numbered layers. Circular imports are treated as lint/build failures.

### 5. Execution Safety Guards
- **Subprocess Isolation**: Subprocess spawning is strictly restricted to the `nexus/execution/` boundary. No other package may execute terminal shells directly.
- **Preflight Check**: The subprocess runner must verify that the `ApprovalRecord` for a privileged step is `APPROVED` before spawning the OS process.
- **Crash Recovery**: An APScheduler sweeper daemon runs every 60 seconds to inspect the `execution_steps` table. Steps that miss the heartbeat threshold are marked as `TIMED_OUT` to prevent infinite blocking.

### 6. Phase 1 Action Point Roadmap
We adopt the 6 Action Points detailed in `blueprint/phases/phase-01-ap-breakdown.md`:
- **AP-101**: Database Foundation
- **AP-102**: Event System & Normalization
- **AP-103**: Memory Manager (Context Compactor)
- **AP-104**: Task Engine Lifecycle
- **AP-105**: Approval Engine Gateways
- **AP-106**: State Machine Integrations

---

## Consequences

### Positive
- Clear separation of concerns: Database schema changes do not leak into execution boundaries.
- Simple dependency graphs: Eliminates circular imports during package boot.
- Safe automated operations: Rogue subprocesses are detected and terminated by the heartbeat sweep.
- Perfect auditing: Perfect history tracking via immutable audit trails.

### Negative
- Higher initial boilerplate due to explicit payload mapping.
- Row-level locking inside SQLite requires careful connection management to avoid deadlocks.

---

## Next Steps

Upon approval of this ADR, Phase 1 implementation begins with **AP-101 (Database Foundation)** to implement the relational model schemas in `nexus/memory/models.py` and run Alembic migrations.
