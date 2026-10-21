# nexus_runtime — Phase 8A Runtime Core

The Runtime Manager **prepares** runtimes and owns **Runtime Sessions**. It never
executes. Given the `nexus_core`-projected inputs of a batch of Execution Packages, it
discovers runtimes through the `RUNTIME`-category Registry view, matches capabilities,
filters health, applies declarative policy, **allocates** exactly one runtime
deterministically, and creates a Runtime Session bound to it — driving the session to
`Ready`, the handoff artifact for the Execution Engine (a later phase).

```
… → Harness → Execution Package → Runtime Manager → Runtime Session → Execution Engine
                                    (this package)         ▲
                                                           └ preparation stops at Ready
```

## What it does (and never does)

**Does:** runtime registration + discovery (Registry *view*), capability matching,
health/availability filtering, declarative policy filtering, deterministic selection +
**allocation**, Runtime Session creation, lifecycle management, event emission, persistence,
telemetry.

**Never:** plans/orchestrates work, edits the repositories it reads, invokes a provider,
launches a process, runs a Work Package, streams output, validates an outcome, performs
recovery, decides an approval. (`docs/v2/runtime/01_RUNTIME_MANAGER.md` §3.)

## Dependency direction (strict)

```
nexus_runtime → { nexus_core, nexus_infra }      (the only imports)
```

RM **never** imports `nexus_planning`, `nexus_context`, `nexus_orchestration`, or
`nexus_harness` (doc 00 §4). It consumes their outputs by value/reference through the
`RuntimeIntake` projection, assembled at the integration boundary, and reuses the Phase 2
persistence mechanism unchanged.

## Determinism

Given identical intakes and an identical Registry snapshot, RM produces identical Runtime
Sessions, Allocations, and event streams. There is no AI and no randomness; identifiers are
pure functions of the Execution Package identity and the attempt ordinal (no timestamps in
identifiers). Wall-clock time is injected (`TimestampSource`) and recorded only in event
payloads (INV-17).

## Module map

| Module | Responsibility |
|---|---|
| `vocabulary.py` | `RuntimeLifecycleState` + reference target-type constants |
| `ids.py` | pure-function id derivation (session / allocation / event / correlation) |
| `events.py` | `runtime.*` event constants + `TimestampSource` + `build_event` |
| `requests.py` | `RuntimeIntake` / `PreparationRequest` — the `nexus_core`-only inputs |
| `validators.py` | fail-fast error hierarchy + intake/output validation (dependency-light root) |
| `lifecycle.py` | legal-transition table, `validate_transition`, `project_state` (ADR-001 fold) |
| `runtime_registry.py` | `RUNTIME`-category view over the Harness Registry + reference `InMemoryHarnessRegistry` |
| `runtime_session.py` | immutable `RuntimeSession` + builder |
| `allocation.py` | selection funnel (`RuntimeSelector`), `Allocation`, capacity `AllocationLedger` |
| `runtime_manager.py` | the `RuntimeManager` service + preparation pipeline |
| `persistence.py` | `RuntimeRepositories` over the Phase 2 `InMemoryRepository` |
| `observability.py` | runtime-scoped counters over the Phase 2 sink |
| `composition.py` | `build_runtime` — dependency-injection wiring (no global state) |

## Usage

```python
from nexus_infra import build_infrastructure
from nexus_runtime import build_runtime, preparation_request  # see tests/helpers for intake builders

infra = build_runtime(build_infrastructure())
infra.manager.register_runtime(runtime_descriptor)          # RUNTIME harness → Registry view
result = infra.manager.prepare(preparation_request)         # → Ready sessions + allocations
```

See `docs/v2/PHASE_8A_RUNTIME_CORE.md` for the implementation architecture and deferred
items, and `docs/v2/runtime/` for the frozen design.
