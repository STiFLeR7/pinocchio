# Testing Guide

How tests are organized, run, and written for the `nexus_core` foundation, and — per §2.1 below — for
every package built on top of it. See `docs/development/DEVELOPMENT.md` §3 for the full, current 31-package
inventory; this guide's per-layer prose below stops narrating each package individually at Phase 6
(`nexus_harness`) purely to stay proportionate — every later package (`nexus_execution`, `nexus_validation`,
`nexus_recovery`, `nexus_reflection`, `nexus_knowledge`, `nexus_workflows`, `nexus_policy`, `nexus_approval`,
`nexus_operations`, `nexus_scheduler`, and the rest) follows the exact same discipline described here
(construct real objects, assert failure not just success, determinism tests where the layer is required to
be deterministic), under its own mirrored `tests/unit/<package>/` directory.

---

## 1. Philosophy

The foundation is pure, deterministic, and infrastructure-free, so its tests are
fast unit tests with no I/O, no network, no database, and no time/randomness
dependence. Every test is reproducible and runs in well under a second total.

The suite verifies the four contract dimensions the type system cannot fully
encode:

- **Schema** — models conform to and round-trip through their canonical schema.
- **Invariants** — architectural invariants (`INV-xx`) hold on object contents.
- **Lifecycle** — only legal state transitions are permitted.
- **Relationships** — references point at the correct kind of object.

## 2. Layout

```
tests/unit/nexus_core/
├── domain/          one test module per domain model
├── state/           state machine + transition tables + core state
├── validation/      schema / invariant / lifecycle / relationship validators
├── registries/      registry Protocol conformance
├── events/          event primitives
└── persistence/     persistence Protocol conformance
```

One test module per source unit; mirror the package structure when adding tests.

The **infrastructure layer** (Phase 2) has its own suite:

```
tests/unit/nexus_infra/
├── factories.py     shared builders for valid domain objects (one source of truth)
├── test_event_store.py / test_event_bus.py / test_event_versioning…
├── test_projections.py / test_snapshots.py
├── test_repositories.py / test_unit_of_work.py
├── test_serialization.py / test_identifiers.py / test_observability.py
└── test_composition.py    end-to-end integration (emit → project → snapshot → replay)
```

`factories.py` builds fully-valid `Event`/`Goal`/`Plan`/`Artifact`/`Policy`/
`Knowledge` objects with deterministic defaults, so infra tests read as intent
rather than construction boilerplate. The integration test in `test_composition.py`
exercises replay equivalence and snapshot-plus-tail-replay (ADR-001 / INV-14/18).

The **planning layer** (Phase 3) has its own suite under
`tests/unit/nexus_planning/` with a shared `helpers.py` (`make_goal`,
`make_capability`, `item`, `planning_env`). Because Planning is required to be
deterministic, `test_determinism.py` asserts that identical Goals and inputs yield
byte-identical Plans, Work Packages, Execution Graphs, and event streams — the
headline Phase 3 guarantee.

The **context-engineering layer** (Phase 4) has its own suite under
`tests/unit/nexus_context/` with a shared `helpers.py` (`make_goal`, `fragment`,
`request`, `context_env`). It mirrors the same discipline: `test_determinism.py`
asserts identical Goals and inputs yield byte-identical Context Packages, items,
conflicts, and event streams, and `test_integration.py` proves the
`Goal → Context → Context Package → Planning` pipeline composes end-to-end (the
package is referenced by `PlanningRequest.context_ref`) with no coupling between
the two layers.

The **orchestration layer** (Phase 5) has its own suite under
`tests/unit/nexus_orchestration/` with a shared `helpers.py` (`gnode`, `gedge`,
`make_graph`, `make_strategy`, `make_request`, `harness`, `orchestration_env`). It
holds the same line: `test_determinism.py` asserts identical Goal / Context / Plan /
Execution Graph / Strategy yield byte-identical Execution Sessions, dependency and
queue state, approvals, Harness/Runtime requests, and event streams, and
`test_integration.py` proves `Planning → Orchestration` composes end-to-end over one
shared infrastructure with no coupling between the layers.

The **harness layer** (Phase 6) has its own suite under
`tests/unit/nexus_harness/` with a shared `helpers.py` (`skill`, `capability`,
`policy`, `context_package`, `work_package`, `strategy`, `artifact`, `hrequest`,
`harness_env`, `standard_env`). It holds the same line: `test_determinism.py` asserts
identical Harness Requests and resolution sources yield byte-identical Execution
Packages, Execution Manifests, and event streams, and `test_integration.py` proves
`Planning → Orchestration → Harness` composes end-to-end over one shared
infrastructure — the Harness compiles Orchestration's output into runtime-ready
packages with no coupling between the layers and no side effects.

### 2.1 Packages built after Phase 6

Every package from `nexus_execution` onward (see `DEVELOPMENT.md` §3 for the full list) has its own
`tests/unit/<package>/` suite following this same shape — a `helpers.py`/`factories.py` shared-builder
module where the package needs one, a `test_determinism.py` where the layer is required to be deterministic,
and `test_integration.py`/`test_guardrails.py` where the layer composes with its neighbors or is
constitutionally forbidden from reaching one. `tests/integration/` holds the cross-cutting suites that
don't belong to one package alone — the full Constitutional Pipeline (`test_constitutional_spine.py`), the
Scheduler (`test_scheduler.py`), the Approval Exchange (`test_approval_exchange.py`), and the production
entrypoint (`test_v2_entrypoint.py`).

**Coverage-gate scope, disclosed honestly:** `pytest`'s `--cov-fail-under=95` gate (§4) currently only
tracks 20 of the 31 v2 packages — the same 20 the `Makefile`'s `PACKAGES` variable lists (see
`DEVELOPMENT.md` §6 for the full list and why). The remaining 11 packages are still run and must still
pass, they're simply not yet coverage-gated; two of them (`nexus_repository`, `nexus_scheduler`) sit below
the 95% floor on their lowest-covered modules today (60% and ~90% respectively, per
`docs/v2/P17_PRODUCTION_READINESS_REPORT.md`) — a known, tracked gap, not silently omitted.

## 3. Running tests

```bash
make test                       # fast: whole core suite, quiet
uv run pytest tests/unit/nexus_core -q

# A single module / test:
uv run pytest tests/unit/nexus_core/domain/test_goal.py
uv run pytest tests/unit/nexus_core/domain/test_goal.py::test_goal_is_frozen
```

`pytest` is configured (in `pyproject.toml`) with `--strict-markers` and
`--strict-config`, and `asyncio_mode = "auto"`.

## 4. Coverage

```bash
make test-cov          # terminal + coverage.xml + htmlcov/
# then open htmlcov/index.html
```

- **Branch coverage** is enabled.
- **Threshold:** `--cov-fail-under=95`. Current actual coverage is **~97%** — the
  floor sits just below real coverage so honest gaps fail the build, but it is
  **not** inflated to a vanity 100%.
- Protocol/abstract stub bodies (`...`), `if TYPE_CHECKING:` blocks, and
  `raise NotImplementedError` are excluded via `[tool.coverage.report]` because
  they are unexecutable by design — excluding them keeps the percentage
  meaningful rather than padded.

> **Do not inflate coverage.** Never write a test whose only purpose is to touch
> lines. If code cannot be meaningfully exercised, either it is dead (remove it)
> or it is a genuine stub (exclude it explicitly with a documented pragma).

## 5. Writing tests

Conventions used throughout the suite:

- **Construct real domain objects** — the models are cheap, frozen Pydantic
  objects; prefer real instances over mocks.
- **Assert immutability** — frozen models must reject mutation and unknown
  fields (`extra="forbid"`); cover at least one such case per model.
- **Assert failure, not just success** — validators must *raise* on bad input
  (`ContractViolation` subclasses) and illegal transitions must raise
  `IllegalTransitionError`. Negative cases are first-class.
- **No silent correction** — a test that expects an invalid object to be
  "cleaned up" is wrong; the contract is fail-fast.
- **Determinism** — never depend on wall-clock time, randomness, ordering of
  unordered collections, or environment. Pass values in explicitly.

Example shape:

```python
import pytest
from nexus_core.domain import Goal
from nexus_core.validation import InvariantValidator, InvariantViolation


def test_goal_rejects_mutation(goal: Goal) -> None:
    with pytest.raises(Exception):  # frozen model
        goal.outcome = "changed"  # type: ignore[misc]


def test_invariant_validator_flags_violation(broken_goal: Goal) -> None:
    with pytest.raises(InvariantViolation):
        InvariantValidator().validate(broken_goal)
```

## 6. What to test when adding a domain model

1. Constructs with valid inputs; rejects `extra` fields and mutation.
2. Schema round-trip is identity-preserving (`SchemaValidator`).
3. Each invariant tied to the model has a passing and a failing case.
4. Lifecycle: legal transitions allowed, illegal ones raise.
5. References resolve to the expected `target_type`.
