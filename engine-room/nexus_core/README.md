# `nexus_core` — Nexus v2 Foundation (Phase 1)

The stable engineering foundation for Nexus v2. Platform primitives only:
immutable domain objects, contract validation, registry interfaces, event
primitives, state primitives, and persistence abstractions.

> If every higher-level subsystem (Context Engineering, Planning, Orchestration,
> Execution, Knowledge) were deleted tomorrow, this package must remain correct.

It contains **no** AI, orchestration, planning, execution, persistence
implementation, scheduling, or API logic — those are later phases. The
architecture is frozen (`docs/v2/`, `adr/`, `contracts/`, `blueprint/v2/`); this
package implements the frozen contracts exactly and never redefines them.

This is a parallel, additive package. It does not modify the v1 `nexus/`
package.

---

## Layout (built in dependency order)

```
nexus_core/
├── contracts/        Step 1 — typed contract primitives (source-of-truth vocabulary)
│   ├── base.py         DomainObject, ValueObject, Reference, Correlation, Constraint, Struct
│   ├── enums.py        shared value ladders + category taxonomies (defined once)
│   └── status.py       per-object lifecycle status enums
├── domain/           Step 2 — the 17 immutable domain models (one per contract)
├── validation/       Step 3 — schema · invariant · lifecycle · relationship validators
├── registries/       Step 4 — the four registry interfaces (ADR-002), no implementations
├── events/           Step 5 — event primitives + emit/consume interfaces (no bus)
├── state/            Step 6 — unified CoreState, generic StateMachine, per-object tables
└── persistence/      Step 7 — Repository/Store/Projection/Snapshot/Serializer/UoW (interfaces)
```

Dependency direction is one-way and acyclic: `contracts → domain →
{validation, events, registries, persistence, state}`. Nothing imports a web
framework, ORM, database, or runtime.

## Design rules

- **Immutable domain objects.** Every model is a frozen Pydantic
  `DomainObject` with `extra="forbid"` — unknown fields and mutation both fail
  fast (no silent correction).
- **One canonical schema per object** (INV-07). Enums are defined once in
  `contracts/enums.py`/`status.py` and reused.
- **References over embedding.** By-id pointers use `Reference`
  (`target_type` + `identifier`); the object graph carries no embedded copies
  (INV-12, INV-27, ADR-003 §3.3).
- **State is a projection.** Per ADR-001 the event log is authoritative; an
  object's `status`/`stage` field is a projection. `state/` provides the
  *rules* (legal transitions) the projection enforces (INV-15); it does not
  drive transitions.
- **Interfaces, not implementations** for registries, events, and persistence —
  `Protocol`s so higher layers depend on abstractions (dependency inversion).
- **Strict everything.** `mypy --strict` clean, `ruff` clean, comprehensive
  unit tests, 100% deterministic behavior.

## Using the foundation

```python
from nexus_core.domain import Goal, Scope
from nexus_core.contracts.enums import Domain, Priority, InterpretationConfidence
from nexus_core.contracts.base import Constraint
from nexus_core.validation import InvariantValidator, LifecycleValidator
from nexus_core.state import machine_for

goal = Goal(
    identity="goal-1",
    outcome="Resolve the authentication failure",
    domain=Domain.SOFTWARE,
    priority=Priority.HIGH,
    confidence=InterpretationConfidence.HIGH,
    constraints=(Constraint(kind="deadline"),),
    scope=Scope(included=("auth",), excluded=("billing",)),
)

InvariantValidator().validate(goal)          # raises ContractViolation on a broken invariant
machine_for("goal").validate_transition(...)  # raises IllegalTransitionError on an illegal move
```

## What is intentionally absent (later phases)

Event bus, event store, state-projection engine, checkpoint store, policy
evaluation engine, capability resolution, runtime/harness implementations,
serialization wire-format (AP-101), any database, and all pipeline engines.
These build *on top of* these primitives without redesigning them.

## Verification

```bash
.venv/Scripts/python.exe -m ruff check nexus_core/ tests/unit/nexus_core/
.venv/Scripts/python.exe -m mypy nexus_core/
.venv/Scripts/python.exe -m pytest tests/unit/nexus_core/ -q
```
