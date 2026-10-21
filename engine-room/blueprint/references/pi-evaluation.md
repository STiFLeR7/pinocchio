# Pi Framework — Evaluation Report

Status: ✅ Complete
Priority: Critical (Must complete before Phase 1)
Repository: https://github.com/earendil-works/pi
Evaluation Date: 2026-06-19
Author: Antigravity Coding Assistant

---

## Background

Multiple Nexus documents mandate the evaluation of the Pi Agent Harness (https://github.com/earendil-works/pi) before implementing orchestration primitives. This report documents the capabilities, limitations, and architectural fit of Pi for the Nexus Control Plane.

---

## Evaluation Questions

### Workflow Execution
- **Does Pi support defining multi-step workflows?**
  *No.* Pi is an interactive, turn-based agent loop (`Agent` or `agentLoop`) that dynamically decides its next step based on prompt history, follow-up queues, and LLM tool selections. It lacks a static DAG, state-chart, or node-and-edge workflow definition schema.
- **Can workflows be paused and resumed?**
  *Yes.* By reducing the append-only JSONL session log, the harness reconstructs state up to the last durable boundary (`leaf`). The host application can call `agent.continue()` to resume execution.
- **Does Pi support conditional branching?**
  *Yes, but dynamically.* Branching is represented as conversation tree forks in the session log. There is no static conditional branching engine.
- **Does Pi support parallel execution?**
  *Yes.* Tool calls in a single turn can execute concurrently (using `toolExecution: "parallel"`), with completion order resolved dynamically.

### State Management
- **Does Pi persist workflow state?**
  *Yes.* The `AgentHarness` records model selections, messages, active tools, system prompts, and queue states.
- **Does Pi support workflow checkpoints?**
  *Yes.* It saves state at turn boundaries and supports "compactions" to summarize and prune conversation logs.
- **Does Pi survive process restarts?**
  *Yes.* Restoring is accomplished by reading and reducing the JSONL file-based session registry on startup.
- **What storage backends does Pi support?**
  *File-based JSONL* (`JsonlStorage`) and *In-Memory* (`MemoryStorage`). It does not ship with built-in SQL database adapters (SQLite/PostgreSQL).

### Agent Orchestration
- **Does Pi support agent lifecycle management?**
  *Yes, but only for single-agent systems.* It manages the prompt-execution cycle of a single agent. It does not provide orchestration for a multi-agent network (e.g., routing between Planning, Execution, and Communication agents).
- **Can Pi route work to different agent types?**
  *No.* The architecture assumes a flat runtime execution pattern.
- **Does Pi support agent failure recovery?**
  *Yes.* The harness detects interrupted runs during recovery and applies configurable policies (e.g., `mark_interrupted`, and blocks automatic retries on non-idempotent tools).

### Task Coordination
- **Does Pi support task queuing?**
  *Yes, in-memory with session persistence.* It provides steering queues (interrupting active turns) and follow-up queues (queuing sequential prompts), but is not a general-purpose task broker.
- **Does Pi support task prioritization?**
  *No.* Queues are FIFO.
- **Does Pi support task dependencies?**
  *No.*

### Scheduling
- **Does Pi support scheduled/cron tasks?**
  *No.* Pi has no scheduling primitives.
- **Can Pi integrate with APScheduler or similar?**
  *Yes.* A host application can invoke Pi CLI or API tasks inside cron triggers, but integration must be built custom.

### Failure Recovery
- **Does Pi handle agent failures with retry?**
  *Yes, manual/programmatic.* The API provides retry hooks via `continue()`, but it lacks automated call-retry mechanisms or circuit breakers.
- **Does Pi support circuit breakers?**
  *No.*
- **What happens on Pi process crash?**
  *State recovery is clean.* The session manager resolves partial writes on restart, logs non-idempotent tool status, and prevents double-execution.

### Persistence
- **What storage backends does Pi use?**
  *JSONL files.*
- **Can Pi use SQLite/PostgreSQL?**
  *Not natively.* The storage interfaces are abstract (`Storage` and `Repo`), meaning SQL adapters could be custom-written, but none are supplied out of the box.

### Observability
- **Does Pi emit structured events?**
  *Yes.* It emits typed events (`agent_start`, `turn_start`, `message_update` for streaming delta text, `tool_execution_start`, `tool_execution_end`, `agent_end`).
- **Does Pi have an audit log?**
  *Yes.* The append-only session log acts as a detailed audit trail of all messages, tools, and harness operations.

---

## Findings

### Summary
Pi is an excellent, production-grade interactive coding agent framework (TypeScript) designed for human-in-the-loop terminal environments. It excels at local session durability, dynamic tool execution, and unified multi-provider LLM wrappers. However, it is not a general-purpose backend orchestrator, nor does it provide structured workflow execution, multi-agent routing, or native relational database management.

### Strengths
1. **Durable Session Design**: The append-only event-reduction model is a robust way to ensure that agent state and history survive process crashes cleanly.
2. **Parallel Tool Execution**: Highly optimized parallel tool executions with order-preservation for LLM context updates.
3. **Steering & Follow-ups**: In-flight loops can be cleanly steered or queued via simple message queues.

### Weaknesses
1. **Language Gaps**: Written in TypeScript, whereas Nexus is built strictly on Python (FastAPI, SQLAlchemy, Pydantic). Integrating Pi would create a split-brain system requiring complex bridging layers.
2. **Single-Agent Focused**: Lacks native constructs for multi-agent networks, task queues, priority levels, or dependency mapping.
3. **No Relational SQL Backend**: It relies on file-based JSONL. Adapting it to relational SQL storage (SQLite/PostgreSQL) with Alembic schema management requires custom re-engineering.
4. **No Static Workflow Engine**: Offers no primitives for defining static DAGs or multi-step execution graphs.

### Architectural Fit Assessment
Pi is an architectural mismatch for the Nexus Control Plane. Nexus requires a Python-native, database-backed (SQLAlchemy + SQLite), multi-agent orchestration system with strict owner-approval gates (Discord/Email) and scheduled jobs (APScheduler). Pi's TypeScript interactive terminal nature and lack of multi-agent and workflow graph routing would force Nexus to build heavy bridge layers, bypassing its core design goals.

---

## Decision

**Chosen Option:** **Option C — Reject**

### Justification
1. **Tech Stack Alignments**: Adopting a TypeScript agent harness in a strict Python backend project violates the tech stack decisions (ADR-006) and increases deployment/maintenance complexity.
2. **Requirements Mismatch**: Pi does not solve multi-agent routing, relational task-priority queues, scheduling, or owner authorization gates. We would end up writing the majority of the orchestrator custom anyway.
3. **Clean Custom Design**: The foundation built in Phase 0 (FastAPI + SQLAlchemy + pytest) is already set up to build a clean, Pythonic, event-driven state machine specifically tailored to Nexus requirements.

### Key Learnings for Nexus Custom Orchestrator:
Although we reject Pi as a direct library dependency, we will borrow its best design concepts:
- **Durable Event Log**: Implement append-only event records in the database (`audit_log`) and reconstruct active task status via database lookups.
- **Normalizing Messages**: Maintain a clear boundary between internal event schemas and LLM prompt schemas.
- **Parallel Tool Calling**: Design execution runners to run tools concurrently when safe, but log results sequentially to keep the context clean.
