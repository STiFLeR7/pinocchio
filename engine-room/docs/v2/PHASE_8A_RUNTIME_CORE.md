# Phase 8A — Runtime Core (Implementation)

**Status:** implemented. Package: `nexus_runtime`. Scope: the Runtime Core — registry,
session, allocation, manager, lifecycle, events, persistence, observability. **No runtime
adapters, no provider integrations, no Execution Engine.** Preparation ends at Runtime
Session creation (`Ready`).

This document records the *implementation* of the frozen Runtime architecture
(`docs/v2/runtime/`) and the observations that surfaced while building it. It modifies **no
ADR, no contract, and no architectural invariant**; where the implementation makes a
choice the design left open, it is noted below as an observation.

---

## 1. Implementation architecture

`nexus_runtime` is a control-plane layer that consumes upstream *outputs* and prepares a
runtime to perform them, exactly as every prior layer consumed the one before it. It is a
**coordinator/preparer**, structurally analogous to the Harness Service (which *compiles*)
and the Orchestration Service (which *coordinates*): deterministic decisions where
decisions are deterministic, delegation of the non-deterministic act (running) to a later
phase, persistence through Phase 2, and event emission.

### Dependency direction (strict — doc 00 §4)

```
nexus_runtime → { nexus_core, nexus_infra }      (the only imports)
```

RM never imports `nexus_planning`, `nexus_context`, `nexus_orchestration`, or
`nexus_harness`. This is **stricter** than the Harness (which imports Orchestration) and is
honored by consuming a `nexus_core`-only projection of the upstream outputs — see §9,
**Observation O-8A-1 (RuntimeIntake)**.

### Module graph (acyclic by construction)

```
vocabulary ── ids ── events
     │          │       │
     └── lifecycle ◄────┘         requests (nexus_core only)
            │                        │
            │                     validators
            ▼                        │
   runtime_registry ─► allocation ◄──┘
            │              │
   runtime_session ◄───────┤
            │              │
        persistence   observability
            │              │
            └──► runtime_manager ◄──┘
                     │
                 composition ──► RuntimeContext
```

`validators.py` imports only the frozen contracts and `requests.py`, staying the
dependency-light root (mirroring the Harness's `validators.py`). The base error is
`RuntimeManagerError` — deliberately **not** `RuntimeError` — so it never shadows the
builtin.

### The preparation pipeline (doc 01 §4, realized)

`RuntimeManager.prepare` drives each intake through:

```
validate intake → create session (Created) → resolve candidates → match capabilities
   → SELECT (deterministic) → reserve → allocate → bind → configure (Prepared) → Ready
   → persist
```

A batch is **atomic**: any intake failure emits `runtime.failed`, releases that intake's
reservation, **rolls back** every already-successful allocation in the batch (no capacity
leak — doc 07 §6), and raises. Nothing is persisted on failure.

### Determinism (doc 01 §5)

Identifiers are pure functions of the Execution Package identity + attempt ordinal
(`ids.py`); selection uses a **total, deterministic** tie-break (declarative preference →
cost preference → Registry's canonical identity order); wall-clock is injected
(`TimestampSource`) and appears only in event payloads (INV-17). Verified by
`test_determinism.py`: the same request through two fresh environments yields byte-identical
sessions, allocations, and `(id, type, payload)` event triples.

---

## 2. Lifecycle realization

Phase 8A implements the **preparation slice** of doc 07's canonical machine as
`RuntimeLifecycleState`:

```
Created ─► Registered ─► Allocated ─► Prepared ─► Ready
   │            │             │           │          │
   └────────────┴─────────────┴───────────┴──────────┴─► Failed ─► Released
   └────────────┴─────────────┴───────────┴──────────────────────► Released
```

| State | Meaning (Phase 8A) | doc 07 mapping |
|---|---|---|
| `Created` | session shell exists; package bound; runtime not yet chosen | `Created` |
| `Registered` | candidates resolved from the Registry and capabilities matched | (preparation detail of `Created`) |
| `Allocated` | one runtime selected, reserved, allocated, and bound to the session | (folded into `Prepared` in doc 07) |
| `Prepared` | adapter configuration rendered | `Prepared` |
| `Ready` | readiness checks pass; eligible for handoff | `Ready` |
| `Released` | allocation returned; capacity freed (teardown) | the release step of `Destroyed` |
| `Failed` | ended on a typed error | `Failed` |

`lifecycle.py` owns the legal-transition table, `validate_transition` (rejects illegal
transitions fail-fast with `IllegalTransitionError`, mirroring the core state machine's
discipline), and `project_state` — the ADR-001 fold that reconstructs a session's state
from its ordered `runtime.*` event-type stream (idempotent; verified in `test_replay.py`).
Sessions are **immutable**: each transition returns a new frozen instance via
`transitioned_to`, while the manager records the driving event — so state remains a
*projection* of the log, not a mutated field.

The execution/teardown states `Running / Paused / Waiting / Completed / Cancelled /
Destroyed` are **deferred to the Execution Engine phase** and intentionally absent (§8).

---

## 3. Registry implementation

`runtime_registry.py` realizes the **"no second registry"** canon (doc 04 §1): the
`RuntimeRegistry` is a `RUNTIME`-category **view** over a `HarnessRegistry`, not a store.

- **`RuntimeRegistry`** (the view): `register` accepts only `HarnessCategory.RUNTIME`
  descriptors (a non-runtime is a fail-fast `ValueError` — the view refuses to widen its
  lens); `get`/`list_runtimes`/`resolve_candidates` all filter to `RUNTIME`; `is_reachable`
  **reads** the Registry-owned `availability` (INV-36 — RM never writes it), treating only
  `AVAILABLE` as reachable and `UNKNOWN` conservatively as *not* reachable (no silent
  optimism).
- **`InMemoryHarnessRegistry`** (reference implementation): ships here because no standalone
  registry phase exists yet — mirroring how in-memory reference registries shipped in
  Harness/Orchestration. Deterministic ordering throughout; `discover_by_capability`
  returns advertisers **candidates-only** (INV-37). Every consumer depends on the
  `HarnessRegistry` Protocol, so the reference is swappable.

Ownership boundary held exactly: **availability/health live in the Registry (INV-36);
allocation lives in RM (doc 04 §6).** RM's `ResourceAllocationState` bookkeeping never
overwrites the Registry's `ResourceAvailability`.

---

## 4. Allocation implementation

`allocation.py` is where allocation lives (doc 06, INV-37). It implements:

- **`RuntimeSelector`** — the deterministic funnel: **resolve → match → health → policy →
  select**. Each stage only removes candidates (or the set is empty → typed error, never a
  silent default). Capability matching is **provider-independent** (INV-32): it compares the
  intake's required capability *references* to a descriptor's `advertised_capabilities` by
  identifier, and **records** satisfied/unsupported on every candidate (doc 05 §2 — never
  silently dropped). Declarative policy (`allowed_runtimes` / `denied_runtimes` /
  `cost_ceiling` filter; `preferred_runtimes` / `cost_preference` tie-break) is **applied,
  never derived** (doc 06 §6) — RM reads it from `runtime_policy` verbatim. The final pick
  is a total order (`preferred_rank`, `cost_rank`, `identity`) so the same inputs always
  choose the same runtime (doc 06 §8).
- **`AllocationLedger`** — RM's own reservation bookkeeping: `reserve` (`AVAILABLE →
  RESERVED`), `allocate` (`RESERVED → ALLOCATED`), `release` (`* → RELEASED`), with
  per-runtime capacity (default 1; overridable via descriptor `metadata["capacity"]`) so a
  batch never double-books a runtime. Illegal ledger operations (reserve at capacity,
  allocate from a non-`RESERVED` state, double-release) are fail-fast `AllocationError`s.
- **`Allocation`** — the immutable reservation record, carrying a deterministic id
  (`f(session id, runtime id)`), referenced by the session (never embedded).

Empty survivor sets map to precise typed errors: `UnresolvedRuntimeError` (nothing
resolved), `CapabilityMismatchError` (nothing eligible), `NoEligibleRuntimeError`
(nothing reachable/permitted). The Execution Engine never selects, allocates, or releases
— it receives an already-bound runtime (doc 06 §11).

---

## 5. Persistence integration

`persistence.py` reuses the Phase 2 mechanism unchanged (doc 00 §4): `RuntimeRepositories`
holds two `InMemoryRepository` instances (`runtime_session`, `runtime_allocation`) keyed by
identity. RM writes **only its own state**; it never writes the repositories it reads from.

"Runtime metadata" (the Runtime Descriptors) is deliberately **not** persisted in a
runtime-owned store: per INV-36 it lives in the Harness Registry, which RM only reads
through the view. Duplicating it would re-own availability/health — precisely what INV-36
forbids. This is the §5 realization of the "no second registry" canon.

---

## 6. Observability integration

Two complementary channels, matching doc 15 / doc 16:

1. **Authoritative — the `runtime.*` event log.** Every fact is a canonical `Event`
   (`producer="runtime"`, `source="nexus_runtime"`, deterministic identifier, shared
   `correlation_identifier` — INV-39) emitted through the Phase 2 event store + bus. Session
   state is a projection of this stream (ADR-001). Events used (all doc 15 canonical except
   `runtime.registered`, see §9): `runtime.registered`, `runtime.candidates_resolved`,
   `runtime.capabilities_matched`, `runtime.session_created`, `runtime.allocated`,
   `runtime.prepared`, `runtime.ready`, `runtime.released`, `runtime.failed`.
2. **Derived — counters.** `RuntimeObservability` increments named counters on the Phase 2
   `Observability` sink (registered / discovered / session_created / allocated /
   session_ready / released / failed) and observes a candidate-resolved gauge. These are a
   convenience for operators and later Supervision; **never authoritative state** (doc 00
   §3). No dashboards are built.

Tracing integration is via the shared `correlation_identifier` on every event: a single
Goal's lineage — Goal → … → Harness → **Runtime** — is one queryable causal stream.

---

## 7. Validation gate (evidence)

| Gate | Result |
|---|---|
| Runtime Registry works | ✅ view + reference registry, 100% covered |
| Runtime Allocation deterministic | ✅ total tie-break; `test_determinism.py` |
| Runtime Sessions created | ✅ `Created → Ready`, immutable, persisted |
| Lifecycle valid | ✅ transition table + `IllegalTransitionError`; illegal rejected |
| Persistence succeeds | ✅ Phase 2 repositories, round-tripped |
| Runtime Events emitted | ✅ 9 `runtime.*` types, deterministic ids |
| Existing phases remain green | ✅ **1750 tests pass** (1281 prior + 469 new) |
| No ADR violated / contract modified / invariant violated | ✅ none touched |

- **Tests:** 469 new (`tests/unit/nexus_runtime/`), **100% line + branch coverage** of all
  14 modules; aggregate repo coverage 98.7% (≥95% gate).
- **Typing:** `mypy --strict` clean across 131 source files.
- **Lint/format:** `ruff` clean (package + tests).
- **Build:** `uv build --wheel` includes `nexus_runtime` (7 packages).
- **Tooling wired:** `Makefile`, `.github/workflows/core-ci.yml`, `pyproject.toml`
  (wheel packages), `.pre-commit-config.yaml` all extended with `nexus_runtime`.

---

## 8. Explicitly deferred (out of Phase 8A scope)

Per the phase constraints, the following are **not** implemented and are deferred to later
phases without architectural redesign (the substrate is designed to accept them):

- **Runtime adapters & provider integrations** — Claude Code, Gemini CLI, Shell, Docker,
  Browser, Python, MCP, remote workers (doc 03, doc 19). RM core stays provider-agnostic.
- **The Execution Engine** — running the Work Package inside the allocated runtime; the
  handoff of a `Ready` session is the boundary (doc 06 §11).
- **Execution/teardown lifecycle** — `Running / Paused / Waiting / Completed / Cancelled /
  Destroyed` and their events (`runtime.started` … `runtime.destroyed`).
- **Supervision concerns** — streaming (doc 08), cancellation (09), timeout (10), progress
  (12), heartbeats, artifact collection (13).
- **Approval callbacks** (doc 14) — the pre-allocation approval gate. Phase 8A selection
  proceeds under the automatic path; the gate slots into stage E of the funnel when the
  callback mechanism lands.
- **Validation, Recovery, Reflection, Knowledge** — downstream subsystems.

---

## 9. Implementation observations (no ADR/contract change)

- **O-8A-1 — `RuntimeIntake` projection.** doc 00 §4 forbids RM from importing
  `nexus_harness`/`nexus_orchestration`, yet RM consumes their outputs. Resolved by
  consuming a `nexus_core`-only projection (`RuntimeIntake`: the embedded Work Package,
  required capability refs, candidate refs, `runtime_policy`, correlation) assembled at the
  integration boundary. This honors the strict dependency direction and the "consume
  outputs, never reach back" rule. **Recommendation:** when the Execution Engine phase
  lands, ship the Harness→Runtime adapter that builds `RuntimeIntake` from an
  `ExecutionPackage` + `ExecutionManifest` + `RuntimeRequest` (it may import all three).
- **O-8A-2 — `runtime.registered` (registry-plane event).** doc 15 §2 enumerates
  *session-scoped* events only; it has no registration event. Phase 8A's Step 1 requires
  registration observability, so `runtime.registered` is emitted at registry-plane scope.
  **Recommendation:** add `runtime.registered` to doc 15 (or a registry-events section) in
  the normal doc-maintenance process. No contract file changed.
- **O-8A-3 — lifecycle naming (`Registered`, `Released`).** The Phase 8A state list
  (Step 5) names `Registered` and `Released`, which are not doc 07 session states. They are
  realized as the preparation-detail state (`Registered`) and the teardown-release state
  (`Released`), mapped in §2. No conflict with doc 07's canonical machine — Phase 8A is a
  strict subset plus these two preparation/teardown markers.
- **O-8A-4 — version-aware capability compatibility deferred.** doc 05 §4 specifies
  name-*and*-version matching, but `Reference` carries only `target_type` + `identifier`
  (no version). Matching is by identifier; version compatibility slots in when capability
  references carry versions. Recorded, not silently assumed.
- **O-8A-5 — allocation ownership wording (carried from Phase 7 §9.1).** The
  `ARCHITECTURE_REVIEW.md` R-1 wording tension ("Orchestration assigns runtimes" vs. INV-37
  "candidates only") is **behaviorally resolved** by this implementation: Orchestration's
  `candidate_harness_refs` are candidates only, and allocation is performed here (doc 06,
  INV-37). The residual *wording* clarification remains a recommendation against the design
  docs, not a behavioral gap — nothing here re-derives policy or allocates upstream.
- **O-8A-6 — tests live in `tests/unit/nexus_runtime/`** (repo convention), not
  `nexus_runtime/tests/` as the phase's suggested tree sketched — matching the wired
  Makefile/CI/coverage layout for the other six packages.

---

## 10. What Phase 8A establishes

A production-grade Runtime Core: it discovers runtimes, allocates them deterministically,
creates Runtime Sessions, manages lifecycle state, persists runtime state, and emits runtime
events — **with no provider executing and no Execution Engine existing.** It is the
permanent substrate on which all future Runtime Adapters and the Execution Engine will
operate without architectural redesign.
