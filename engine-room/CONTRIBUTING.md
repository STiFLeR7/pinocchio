# Contributing to Nexus

> **This file covers Nexus v1** (`nexus/`, the Discord-fronted control plane). Contributing to the
> v2.5.0 (`nexus_*`, 32 packages, “Accountable Goal Execution”)? See the
> [v2 release report](docs/releases/V2_5_RELEASE_REPORT.md) for its scope and evidence, and
> [v2 contribution guide](docs/development/CONTRIBUTING.md) for the frozen architecture and `make check`
> gate. This file's rules below remain specific to Nexus v1. See [docs/README.md](docs/README.md) if
> you're not sure which codebase you're working in.

> Read [docs/RULES.md](docs/v1/RULES.md) before contributing. These rules are non-negotiable.

---

## Core Principle

Nexus is a **production-grade orchestration control plane**, not a chatbot or prototype.

Every contribution must maintain:

1. **Determinism** — orchestration logic must not depend on LLM decisions
2. **Persistence** — all state changes must survive restarts
3. **Auditability** — every action must produce a traceable event
4. **Testability** — every component must be testable in isolation
5. **Governance** — no execution without approval

---

## Mandatory Thinking Process

Before implementing anything:

1. Understand requirements fully
2. Identify architectural implications
3. Identify dependencies
4. Identify failure modes
5. Identify testing requirements
6. Produce an implementation plan
7. Execute

**Never jump directly into coding.**

---

## Architecture Before Code

Implementation must never begin without architectural clarity.

Required sequence:

```
Understand → Model → Visualize → Design → Review → Implement
```

When architecture changes, always generate:
- Component diagram
- Data flow diagram
- Sequence diagram
- Failure path diagram

---

## Blueprint Requirements

Every phase, action point, implementation, bug, resolution, and decision **must** be documented inside `blueprint/`.

Documentation is not optional. Documentation is part of implementation.

Structure:

```
Phase → Action Point (AP) → Implementation → Tests → Documentation
```

See [blueprint/README.md](blueprint/README.md) for the blueprint memory system.

---

## Code Standards

### Python Style

- Python 3.11+
- Full type annotations (`from __future__ import annotations`)
- Pydantic v2 models for all data structures
- structlog for all logging (no `print()`, no bare `logging`)
- No global mutable state

### Naming

```python
# Models: PascalCase
class TaskRecord(BaseModel): ...

# Functions/methods: snake_case
def create_task(request: TaskRequest) -> Task: ...

# Constants: UPPER_SNAKE_CASE
DEFAULT_RETRY_COUNT = 3

# Modules: snake_case
# nexus/core/task_engine.py
```

### Logging

Every subsystem emits structured logs. Required fields:

```python
log.info(
    "task.created",
    task_id=task.id,
    component="task_engine",
    correlation_id=ctx.correlation_id,
)
```

Never use `print()`. Never use bare `logging.info()`.

### Error Handling

Never swallow exceptions silently. Every exception must:

1. Be logged with full context
2. Produce an audit event
3. Follow a defined recovery path

```python
try:
    result = await execute_agent(request)
except AgentExecutionError as e:
    log.error("execution.failed", task_id=request.task_id, error=str(e))
    await audit.record(ExecutionFailedEvent(task_id=request.task_id, reason=str(e)))
    raise
```

---

## Testing Requirements

Every feature requires tests at all three levels:

| Level | Location | Purpose |
|---|---|---|
| Unit | `tests/unit/` | Test individual components in isolation |
| Integration | `tests/integration/` | Test component interactions with real dependencies |
| E2E | `tests/e2e/` | Test complete workflows end-to-end |

**No feature is complete without tests.**

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest --cov=nexus --cov-report=html
```

---

## Git Workflow

### Branch Naming

```text
feat/phase-0-ap1-repository-structure
fix/task-engine-state-recovery
test/approval-workflow-coverage
docs/blueprint-phase-0-decisions
```

### Commit Messages

Use conventional commits:

```text
feat(task): implement task lifecycle state machine
fix(approval): persist approval state on Discord disconnect
test(execution): add end-to-end Gemini runner coverage
docs(blueprint): record phase-1 architecture decisions
refactor(memory): centralize Memory Manager access
```

### Workflow

```bash
# 1. Create branch
git checkout -b feat/phase-0-ap1-foundation

# 2. Implement with tests
# ... code ...

# 3. Verify tests pass
pytest

# 4. Commit meaningfully
git commit -m "feat(foundation): initialize project structure with FastAPI skeleton"

# 5. Push
git push origin feat/phase-0-ap1-foundation

# 6. Open PR with description referencing blueprint AP
```

---

## Dependency Management

Dependencies are managed via `pyproject.toml`.

```bash
# Install all dependencies including dev
pip install -e ".[dev]"

# Add a new dependency
# Edit pyproject.toml, then:
pip install -e ".[dev]"
```

---

## Architecture Constraints (Non-Negotiable)

| Constraint | Rule |
|---|---|
| Memory | All state must persist to SQLite/Postgres via Memory Manager |
| Routing | Agent routing must be rule-based, never LLM-dependent |
| Execution | No execution without an approval record |
| Integrations | All adapters must go through Event Gateway |
| State | No private state in integrations — all state belongs to Nexus |
| Models | All LLM calls must go through the Model Router abstraction |
| Commands | No arbitrary shell command execution |
| Repositories | Only allow-listed repositories may be executed against |

Violating these constraints is grounds for immediate PR rejection.

---

## File Creation

The following files are created automatically when you run `./scripts/new_ap.sh`:

```
blueprint/phases/phase-{N}/AP-{N}/
├── SPEC.md
├── IMPLEMENTATION.md
├── DECISIONS.md
└── STATUS.md
```

---

## Questions?

If requirements are ambiguous, conflicting, or incomplete — **stop and ask**.

Never guess. Never invent requirements. Never assume business logic.

Open an issue with precise questions.
