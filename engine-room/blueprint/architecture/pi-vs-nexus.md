# Architectural Comparison: Pi Core vs. Nexus Control Plane

This document compares the systems-design architectures of the **Pi Framework Core** and the **Nexus Control Plane** across critical operational axes.

---

## Architectural Comparison Matrix

| Axis | Pi Core Architecture | Nexus Control Plane Architecture |
|---|---|---|
| **Primary Paradigm** | **Interactive Assistant**: Built for human-in-the-loop CLI/TUI sessions. Direct stdin/stdout feedback loops. | **Autonomous Control Plane**: Built for headless, unattended background operations with API-driven execution. |
| **Language & Platform** | **TypeScript (Node.js/Bun)**: Focused on package monorepos, npm locks, and fast runtime scripting. | **Python 3.12+ (FastAPI/SQLAlchemy)**: Focused on type safety, data schemas, and background job scheduling. |
| **State & Storage Model** | **Session Log Trees (JSONL)**: State is reconstructed dynamically by parsing and reducing an append-only JSONL event file. | **Relational ORM (SQLite + Alembic)**: Strongly typed database schemas with tables (`tasks`, `approvals`, `executions`) and migrations. |
| **Concurrency Model** | **Single-Threaded Event Loop**: Uses JS `Promise.all` for parallel tool execution under Node's single-threaded event loop. | **Multi-Tasking Worker Pools**: Uses `asyncio` combined with background queues and scheduled tasks (APScheduler). |
| **Governance & Safety** | **Implicit Local Permissions**: Runs with the host user's full permissions. Requires external micro-VMs or sandboxes for safety. | **Explicit Approval Gates**: Built-in SQLite approval records. Strict Discord owner User ID verification blocks actions until approved. |
| **Observability** | **Subscriber Streams**: Event emitters broadcast stream deltas and tool events to local console/UI listeners. | **Immutable Audit Logs**: Immutable DB-backed audit table (`audit_log`) and persistent logging via `structlog`. |

---

## Detailed Structural Analysis

### 1. State Modeling: JSONL Trees vs. Relational Tables
- **Pi Core**: Uses trees of conversation nodes. A `leaf` entry marks the active path. While elegant for branching dialogues (forking conversation paths), it lacks index support, relational constraints (foreign keys), or multi-entity query operations.
- **Nexus**: Uses structured relational mappings. Entities (tasks, approvals, executions) are distinct tables connected by foreign key relations (`task_id`, `approval_id`) with cascade operations. This enables complex query indices, fast analytical reports, and strict data integrity.

### 2. Execution Safety: Sandbox vs. Approval Gates
- **Pi Core**: Treats sandboxing as an external infrastructure concern (e.g. running the harness inside Docker or Linux micro-VMs like Gondolin). It provides no runtime permission system within the loop itself.
- **Nexus**: Integrates authorization gates directly into the database lifecycle. An execution cannot run unless an explicit `ApprovalRecord` with status `approved` and a valid owner `decided_by` field exists.

### 3. Concurrency and Async Task Pools
- **Pi Core**: Uses Node's microtask queue. While suitable for quick I/O bounds, it struggles with CPU-bound orchestrations or managing persistent background workers that survive system crashes.
- **Nexus**: Uses Python's `asyncio` loop integrated with FastAPI's background workers. SQLite WAL mode ensures database writes are non-blocking, and background workers operate safely concurrently without memory corruption.
