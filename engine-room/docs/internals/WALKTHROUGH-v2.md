# Nexus v2 — Code Walkthrough

This is a code-level tour for someone reading the v2 implementation for the first time. It is not a
design spec (that's `docs/v2/ARCHITECTURE_CONSTITUTION.md` and the numbered `docs/v2/NN_*.md` docs) and
not an operations manual (that's `docs/v2/OPERATOR_GUIDE.md`). This document exists to answer one
question: **given the source tree, where do I actually start reading, and how does a request move
through it?**

Every claim below is grounded in the code as of tag `v2.0.0` (commit `07097ac`) — file paths, function
names, and enum values you can `grep` for yourself.

---

## 1. Two codebases share one repository

`nexus/` is v1 — a Discord-bot-fronted control plane (`nexus/__main__.py` boots a `uvicorn` ASGI server).
Everything under `nexus_*/` (31 packages) is v2 — a from-scratch, event-sourced constitutional reasoning
spine. They share a git history and a `pyproject.toml`, and nothing else: zero imports in either
direction, no shared schema, no shared process. If you're reading v2 code, you can ignore `nexus/`
entirely. This walkthrough only covers v2.

## 2. Where execution starts

```
python -m nexus_scheduler   # or the `nexus-v2` console script
```

`nexus_scheduler/__main__.py` is the only thing that makes v2 runnable as a process. Read its module
docstring first — it explains its own boundary better than this document can: it boots the platform and
calls `Scheduler.tick(now)` in a loop against the real wall clock. It authors zero Goals — registering
work is a caller concern via `Scheduler.schedule_goal` / `schedule_operation`, the same composition-root
API `bootstrap()` itself wires. Three things `bootstrap()` does differently from every test in this
codebase, and why:

| Production seam | Test default | Why production needs the difference |
|---|---|---|
| `build_durable_infrastructure(db_path, ...)` | in-memory infra | a real process needs the durable SQLite log to survive a restart |
| `_RealTime()` (wraps `nexus_scheduler.events.system_now`) | `FixedTimestampSource` | tests need reproducible timestamps; a real process needs an advancing clock — RC2's whole defect class (§7 below) exists because this difference was, for a while, insufficiently handled |
| `LoggingObservability()` | the silent no-op default | a real process needs its instrumentation to reach somewhere |

Everything else `bootstrap()` does is call existing composition roots unchanged: `build_constitutional_pipeline`, `build_approval_exchange`, `build_operations`, `build_scheduler`. There is no v2-specific wiring logic beyond assembling these four calls into one `PlatformContext`.

## 3. The composition-root pattern

Nearly every package in v2 follows the same shape, and once you recognize it you can read any package in
about the same amount of time:

```python
def build_<name>(infrastructure: InfrastructureContext, ..., now: TimestampSource = SystemTimestampSource()) -> <Name>Context:
    ...
```

- `infrastructure` is always the same `InfrastructureContext` from `nexus_infra` — one durable (or
  in-memory) event log shared by the whole platform. Nothing in v2 has its own private datastore.
- `now` is a `TimestampSource` — every subsystem re-declares its own timestamp-source protocol/class
  rather than importing an earlier layer's (a deliberate dependency-direction discipline, checked by
  `test_guardrails.py` files across the tree). Tests inject `FixedTimestampSource`; only the real
  entrypoint injects a wall clock.
- The returned `<Name>Context` is an immutable dataclass bundling the engine plus whatever repositories/
  observability it needs. Callers never reach past it into internals.

If you want to understand any one package, its `composition.py` (or the `build_*` function in
`__init__.py`/a small `composition` module) is where to start — it tells you exactly what that package
depends on, because it's the only place those dependencies are ever assembled.

## 4. The package map

v2 is organized around the Architecture Constitution's capability model — each capability has exactly one
constitutional owner (INV-02: no two packages may own the same decision). Reading each package's own
`__init__.py` docstring is the fastest way to understand its contract; the table below is a map, not a
replacement for that.

**Reasoning / Grounding plane** (understand the request and the world):
| Package | Owns |
|---|---|
| `nexus_intent` | Understanding operator intent → `Goal` (the Understand capability) |
| `nexus_engineering` | Engineering reasoning → `EngineeringStrategy` (the Reason capability) |
| `nexus_repository` | Understanding repositories — facts only, no reasoning |
| `nexus_history` | Reconstructing historical operational facts — facts only, no reasoning |
| `nexus_estimation` | Quantitative assessment (complexity/duration/cost/confidence) — feeds Engineering Intelligence |
| `nexus_context` | Fusing intent + grounding into one immutable Context Package |

**Planning / Governance plane**:
| Package | Owns |
|---|---|
| `nexus_planning` | Goal → Plan, Work Packages, Execution Graph, Execution Strategy, Capability requirements |
| `nexus_policy` | Every governance decision (`DecisionRequest` → `PolicyEvaluation`); fail-closed by default |
| `nexus_orchestration` | Deciding what becomes executable, when, and what's waiting — never executes |
| `nexus_harness` | Compiling Orchestration's requests into runtime-ready Execution Packages/Manifests |

**Execution plane**:
| Package | Owns |
|---|---|
| `nexus_runtime` | Discovering, matching, and allocating exactly one runtime per Execution Package — never executes |
| `nexus_runtime_adapters` | The generic adapter ecosystem/registry a provider plugs into |
| `nexus_runtime_claude` / `nexus_runtime_gemini` / `nexus_runtime_shell` | Provider-specific adapters (the only place Claude/Gemini/shell-specific code lives) |
| `nexus_execution` | Actually running a Ready Runtime Session and recording canonical `runtime.*` events |

**Post-execution plane**:
| Package | Owns |
|---|---|
| `nexus_validation` | Judging whether execution achieved its objective, from deterministic evidence alone (never the runtime's self-report) |
| `nexus_recovery` | Deciding what happens after a failure — classifies, applies policy, produces a Recovery Plan |
| `nexus_reflection` | Analytical layer over completed history — detects patterns, advisory only |
| `nexus_knowledge` | Durable operational memory — judges Reflection's candidates against a Persistence Policy |

**Fusion, governance-of-autonomy, and operator-facing layers**:
| Package | Owns |
|---|---|
| `nexus_workflows` (see §5) | Fuses all of the above into one durable Goal→Knowledge pipeline |
| `nexus_human_interaction` | The façade over the pipeline — submit, inspect, replay, restart, explain |
| `nexus_approval` | Approval coordination — completes the governance loop when Actuation pauses at a gate |
| `nexus_operations` | Read-only observation surface — active sessions, health, replay/restart inventories |
| `nexus_scheduler` | Execution *timing* — when a Goal enters the platform, and governed autonomy (Manual/Governed/Fully-Automatic) |
| `nexus_integration` | Migration primitives (Recorded Shadow Adjudication, ADR-008) — not used by any live path yet |

**Consumers, not platform extensions** (each composes existing engines; none introduces a new
capability, contract, or ADR): `nexus_research` (autonomous research workflow), `nexus_briefings`
(operational briefings), `nexus_operator` (operator session experience). All three are currently unwired
from any entrypoint — see `docs/v2/OPERATOR_GUIDE.md`'s subsystem-map footnotes for which packages this
applies to and why that's a known, documented gap rather than an oversight.

**Foundation**: `nexus_core` (domain objects, contracts, registry/event/persistence interfaces — zero
business logic) and `nexus_infra` (concrete event store, event bus, projections, snapshots, unit of work
— the one thing every other package depends on).

## 5. The Spine: one Goal→Knowledge pipeline

`nexus_workflows/spine/` is the single most important package to read after the entrypoint, because it's
where all the individually-built engines above actually get driven end-to-end. Its own docstring
(`nexus_workflows/spine/__init__.py`) states the pipeline shape directly:

```
Intent → Engineering → Context → Planning → Execution Actuation
    → [Execution→Validation seam] → Validation → Recovery → Reflection → Knowledge
```

Concretely, `SpineStage` (`nexus_workflows/spine/model.py`) enumerates nine stages, `ORDERED_STAGES` is
`tuple(SpineStage)` in that fixed order:

```python
class SpineStage(StrEnum):
    INTENT = "intent"
    ENGINEERING = "engineering"
    CONTEXT = "context"
    PLANNING = "planning"
    ACTUATION = "actuation"       # Orchestration → Harness → Runtime → Execution, bridged
    VALIDATION = "validation"
    RECOVERY = "recovery"
    REFLECTION = "reflection"
    KNOWLEDGE = "knowledge"
```

`ACTUATION` is not a thin passthrough — it's where Orchestration, Harness, Runtime, and Execution actually
run, bridged together by `nexus_execution/actuation/` (see §7). The spine doesn't reimplement any of
those four packages; it drives them.

**Entry point into the spine:** `ConstitutionalPipeline.run(request: SpineRequest, *, control:
SpineControl | None = None) -> SpineRun` in `nexus_workflows/spine/coordinator.py`. Read `SpineRequest`
(`nexus_workflows/spine/model.py`) next — it's the one thing every stage ultimately derives its identity
from:

```python
@dataclass(frozen=True, slots=True)
class SpineRequest:
    identity: str
    request_text: str            # the raw operator request — Intent Resolution turns this into a Goal
    work_items: tuple[WorkItemSpec, ...]
    knowledge_subject: str
    scope: str
    ...
    @property
    def pipeline_session_id(self) -> str:
        return f"pipe-{self.identity}"       # stable per request; a restart reuses it
    @property
    def correlation(self) -> str:
        return self.correlation_identifier or f"cor-{self.identity}"
```

`run()` replays the durable log to find out which stages have already completed for this request
(`_seed`, see §7 — this is the exact function RC2 rewrote), then drives every remaining `ORDERED_STAGES`
entry in order, each stage's engine invoked through its own composition-root context. `SpineControl` lets
a run stop gracefully after a named stage (`stop_after_stage`) or mid-execution
(`control.actuation`) — the mechanism a later restart or an approval resumption both rely on.

## 6. Durable event sourcing — the one substrate everything shares

`nexus_infra` gives every subsystem the same append-only event log (SQLite/WAL in production, in-memory
for tests). Two facts about it explain a lot of the rest of the codebase's shape:

1. **Identical (identifier, content) is a safe no-op; identical identifier with different content is an
   error.** `nexus_infra/durable.py`'s `DuplicateEventError` is raised only in the second case — the
   first is silently absorbed (`EVENT_DUPLICATE_IGNORED`). This is *why* restart-safety code across the
   tree looks like "check if this exact fact is already recorded, and if so, no-op" rather than "always
   append." Get the identity computation wrong (base it on the wrong scope) and you get one of two
   failure modes: a spurious crash (colliding on genuinely different content), or silent data loss (two
   different facts wrongly treated as the same one — see §7).
2. **Nothing is ever mutated or deleted.** Every "current state" you see anywhere in v2 (a `Goal`, a
   `Plan`, an `ExecutionState`) is a projection — reconstructed by scanning the log for events of a
   particular type and folding them, not read from a row that gets updated in place. This is why replay
   and restart are cheap to reason about: reconstruction is a pure function of "which events exist,"
   never of "what mutable state happens to be sitting around."

## 7. Worked example: how a Goal's identity actually flows (and where it broke)

This is the single best way to see how the pieces in §§3–6 fit together, because it's a real defect class
(found in RC1, fully root-caused and fixed in RC2 — `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`) that
touched exactly the seams this walkthrough has been describing.

**The shape of the bug, everywhere it occurred:** a value that scopes an event to *this specific goal*
was dropped in favor of a narrower or wrong key at one integration seam, so two different goals sharing
that narrower key collided.

- `nexus_execution/actuation/dispatch.py`'s `_project_intake` builds a `package_identity` for each work
  item. Before RC2: `f"actuation-pkg-{node.identifier}"` — unique only within one plan, not across goals.
  Two goals whose plans both produce a node keyed `"draft"` got the *same* Runtime Session identity. Now:
  `f"actuation-pkg-{session_identity}-{node.identifier}"` — `session_identity` is Orchestration's
  Execution Session id, `session-{goal}-v{version}`, which *is* goal-scoped.
- `nexus_workflows/spine/bridge.py`'s `_node_scopes` looked up runtime/validation event scopes by node
  identifier alone. Now it takes the pipeline's own `session_identity` and filters by a `-{session_identity}-`
  marker before including a scope in the result — the same fix shape, one layer up.
- `nexus_workflows/spine/coordinator.py`'s `_seed` (called from `run()`, §5) reconstructed "the most
  recent Goal/Strategy/Plan/ExecutionState in the log" with no filter at all. A second goal sharing the
  durable log would silently adopt the first goal's already-completed state and skip its own pipeline run
  entirely — while still reporting success. This was the most severe of the three, because it corrupted
  silently rather than crashing. The fix: derive `goal_identity = f"goal-{request.identity}"` (the same
  identity Intent Resolution derives for this exact request) and match Goal/Strategy/Plan/ExecutionState
  against it via each artifact's own goal-reference field (`Plan.parent_goal`, `ExecutionState.goal_ref`,
  `EngineeringStrategy.subject_identifier`) — never by recency, never by a value the Scheduler might
  deliberately share across occurrences.

**A trap worth knowing about if you're about to write a similar fix:** the first fix attempt filtered by
`request.correlation_identifier` instead of goal identity. That's wrong, because `Scheduler._dispatch`
(`nexus_scheduler/scheduler.py`) *deliberately* reuses one `correlation_identifier` across every occurrence
of a recurring schedule, by design, for cross-occurrence tracing. Filtering by correlation broke recurring
schedules the same way the original bug broke concurrent goals. The lesson generalizes: when scoping
something to "this goal," use a value that is unique per goal, not a value that happens to usually be
unique per goal. `session_identity`, `goal_identity`, and the `Plan`/`ExecutionState`/`EngineeringStrategy`
goal-reference fields are the real goal-scoped identifiers in this codebase; correlation and node
identifiers are not, even though they often look like they are in a single-goal test.

## 8. Tests mirror the package tree

`tests/unit/<package>/` mirrors `nexus_*` 1:1 (`tests/unit/nexus_workflows/spine/test_coordinator.py`
tests `nexus_workflows/spine/coordinator.py`, etc.). Most packages also carry a `test_guardrails.py` —
these aren't behavioral tests, they're architecture-fitness tests that import-check a package's
dependency direction (e.g. `nexus_scheduler`'s guardrail is what caught an early entrypoint draft
importing `nexus_runtime` directly, in violation of the Scheduler's "timing only" boundary). If you add a
new cross-package import, check whether the package you're importing from already has a guardrail test
for it — it will tell you immediately if the direction is disallowed.

`tests/integration/` holds cross-subsystem, real-durable-log tests — `test_constitutional_spine.py` (the
whole Goal→Knowledge pipeline, including RC2's `test_two_goals_with_identical_work_item_keys_do_not_collide`
and `test_replay_after_two_concurrent_goals_reconstructs_each_independently`), `test_scheduler.py`,
`test_approval_exchange.py`, `test_v2_entrypoint.py` (drives `nexus_scheduler/__main__.py`'s `bootstrap()`
+ `run_service()` directly). If you want to see a whole request lifecycle exercised in one place, these
are the files to run and read, not the unit tests.

## 9. Where to go deeper

This document is a map, not the territory. For the design rationale behind any package, read its own
`__init__.py` docstring first, then the matching `docs/v2/NN_*.md` doc. For the full constitutional model
(13 capabilities, 39 invariants, ADR series): `docs/v2/ARCHITECTURE_CONSTITUTION.md` and
`docs/v2/99_ARCHITECTURAL_INVARIANTS.md`. For running the platform: `docs/v2/OPERATOR_GUIDE.md`. For what
shipped in `v2.0.0` and what's still open: `docs/v2/V1_RELEASE_READINESS_REPORT.md`,
`docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`, and `docs/v2/V2_RELEASE_EXECUTION_REPORT.md`.
