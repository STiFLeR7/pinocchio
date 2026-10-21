# Nexus Final Architecture Review

This report provides the final pre-implementation review of the Nexus orchestrator architecture, evaluating each logical subsystem and analyzing the most valuable architectural decisions that guarantee safety, durability, and operational excellence.

---

## 1. Subsystem Architecture Review

### 1.1. Project Brief (`00_BRIEF.md`)
- **Strengths**: Clear focus on a single operator (Hill Patel) using familiar communication interfaces (Discord/Email) and target execution tools (Gemini CLI and Claude Code). Establishes that orchestration, state persistence, and auditability are the core products.
- **Risks**: High dependency on third-party channels (Discord API rate limits/outages) for critical operations.
- **Missing Pieces**: Concrete multi-tenant scaling path (intentionally out of scope, but poses future rework risk).
- **Future Concerns**: Transition from single-user to multi-user RBAC requires altering database primary keys and state filtering logic.

### 1.2. High-Level Architecture (`01_ARCHITECTURE.md`)
- **Strengths**: Strict 6-layer division with absolute boundaries. Business logic is insulated from the external communication adapters and the raw runner environments.
- **Risks**: Latency accumulation through multi-layered serialization and event routing.
- **Missing Pieces**: Performance tuning metrics and database pooling thresholds.
- **Future Concerns**: Scale bottleneck inside the monolithic workflow orchestrator when parallel task loads increase.

### 1.3. Critical Constraints (`05_CRITICAL_CONSTRAINTS.md`)
- **Strengths**: Non-negotiable rules preventing arbitrary commands, unauthorized mutations, and silent agent operations. Human-in-the-loop is enforced programmatically.
- **Risks**: Extremely strict constraints could restrict the agent's productivity on highly interactive tasks.
- **Missing Pieces**: Handling of emergency bypass codes if the operator is locked out of Discord.
- **Future Concerns**: The requirement to never mutate a repository without approval may block auto-remediation loops.

### 1.4. System Integrations (`04_INTEGRATION_SPECS.md`)
- **Strengths**: Outlines async SMTP (`aiosmtplib`) and Discord bot integrations, plus OpenRouter fallback trees.
- **Risks**: OpenRouter API updates or sudden breaking changes can cause model chain lookup failures.
- **Missing Pieces**: Local mocked integration clients for offline testing.
- **Future Concerns**: Adapting to non-SMTP notifications (e.g. Twilio, WhatsApp API) will require adding a dedicated notify adapter package.

### 1.5. Agent Design (`03_AGENT_DESIGN.md`)
- **Strengths**: Treats LLMs as pure reasoning engines. The agent planner generates steps but has no capability to execute them without Orchestrator routing.
- **Risks**: Bad model planning could lead to infinite loops of failed command runs.
- **Missing Pieces**: Self-correction planning loop guidelines.
- **Future Concerns**: Maintaining planning consistency when switching between models with varying context sizes.

### 1.6. Memory Architecture (`08_MEMORY_ARCHITECTURE.md`)
- **Strengths**: High resilience to crashes. Restoring state depends entirely on replaying the immutable event ledger.
- **Risks**: As the ledger grows, replaying logs from scratch on every startup will degrade performance.
- **Missing Pieces**: Automated database vacuum/compaction jobs.
- **Future Concerns**: Transition from SQLite to PostgreSQL will require database-specific syntax migration.

### 1.7. Runtime Design & Mapping (`runtime-to-code-mapping.md`)
- **Strengths**: Clear separation of durable (first-class) primitives and derived (ephemeral) primitives.
- **Risks**: Complexity of maintaining transaction lock mappings in Python's async event loops.
- **Missing Pieces**: Deadlock detection routines for SQLite.
- **Future Concerns**: SQLite row locking (`SELECT FOR UPDATE`) has limited support, which can cause locks to fail under high write concurrency.

### 1.8. Database Design (`database-design.md`)
- **Strengths**: Strongly typed relational schema with foreign key cascades, WAL mode, and indices on query filters.
- **Risks**: Relational overhead for frequently updated columns like stdout logs.
- **Missing Pieces**: Alembic migration downgrade testing guidelines.
- **Future Concerns**: Rapid disk write amplification in WAL logs due to continuous subprocess output streams.

### 1.9. Event Model (`event-model.md`)
- **Strengths**: Frozen Pydantic schemas with mandatory correlation IDs for end-to-end tracing.
- **Risks**: High CPU deserialization cost if event frequency rises sharply.
- **Missing Pieces**: Dead-letter queue handling for unroutable events.
- **Future Concerns**: Schema compatibility versions for event payloads when migrating settings.

### 1.10. Service Boundaries (`service-boundaries.md`)
- **Strengths**: Layered package boundaries preventing circular imports during boot.
- **Risks**: Strict boundary rules can make adding features that span multiple domains verbose.
- **Missing Pieces**: Automated imports enforcement linter.
- **Future Concerns**: Code refactoring required if a single layer grows too large and needs splitting.

---

## 2. Most Valuable Architectural Decisions

### 2.1. ContextFrame as Derived State
```
Checkpoint (WorkflowCheckpointRecord)
+
Audit Log Replay (AuditLogRecord)
=====================================
ContextFrame (Compiled Ephemeral Prompt)
```
- **Why it is superior**: Traditional agent frameworks save the active prompt history as a mutable text file or database row. This makes history fragile: if the agent writes garbage, the history is corrupted. In Nexus, the `ContextFrame` is compiled dynamically. We load the latest database checkpoint and replay subsequent audit logs up to the current timestamp. If we need to alter how context is formatted or prune token noise, we update the `ContextCompiler` code without changing the underlying database logs.

### 2.2. Append-Only Audit Ledger (`audit_logs`)
- **Replayability**: Since all state transitions are logged as append-only entries, we can reconstruct the state of the orchestrator at any historical millisecond by replaying the log stream.
- **Auditability & Debuggability**: Developers can trace every decision made by the system by filtering the ledger on a single `correlation_id`.
- **Recovery Benefits**: If the system reboots mid-execution, we re-evaluate the ledger to identify what step was running and resume execution seamlessly.

### 2.3. Execution Heartbeats
- **Orphan Detection**: Subprocesses run independently of Python. If the python daemon crashes, the subprocess continues running. When Nexus boots back up, the Heartbeat Sweeper detects processes that missed their heartbeat update and terminates them safely.
- **Recovery**: Orphaned runs are transitioned to `TIMED_OUT` state, clearing execution slots.
- **Long-Running Management**: Prevents hanging command scripts from blocking the execution queue indefinitely.

### 2.4. Decoupled Payload Mapping
```
Provider Payload (e.g. OpenRouter JSON)
↓
Gateway Schema (Pydantic BaseEvents)
↓
Domain Model (SQLAlchemy Records)
```
- **Lock-In Reduction**: By placing mapper functions at the OpenRouter and Discord network boundaries, we decouple internal state engines from external APIs. If OpenRouter updates its API contract, we only modify the gateway mapper, leaving our task engine and database models untouched.

### 2.5. Database-Backed Approval Gates
- **Why Governance Remains Deterministic**: Typical systems store approval states in memory or in Discord channel states. If the Discord bot disconnects, the approval state is lost, and the system can bypass the check. Nexus stores approval gates in the `approvals` database table. The execution engine performs a database query for an `APPROVED` record before launching any subprocess. If the record is missing or expired, execution is blocked, regardless of the Discord connection status.
