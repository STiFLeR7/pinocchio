# Nexus v2 — Operator Guide

Status: **Written for the constitutional spine as it exists at P17** (December 2026 audit), and updated
in place for the RC1 and RC2 hardening passes. This guide describes the `nexus_*` v2 packages built
across programs P0–P16 — an event-sourced constitutional reasoning platform — not the currently-deployed
v1 product (`nexus/`, the Discord/FastAPI pilot). See `docs/v2/P17_PRODUCTION_READINESS_REPORT.md` for
the gap between "built and tested" and "deployed," `docs/v2/RC1_PRODUCTIZATION_REPORT.md` for the
production entrypoint and release-engineering pass, and `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` for
the cross-goal execution-identity fixes referenced in §9.

---

## 1. Architecture overview

Nexus v2 is built on one governing sentence: **runtime executes; Nexus thinks about execution.**
Everything the platform does is either *reasoning about* work (owned by Nexus) or *doing* work (owned by
a replaceable runtime, behind a Harness boundary). The full narrative and its 39 ratified invariants live
in `docs/v2/ARCHITECTURE_CONSTITUTION.md` and `docs/v2/99_ARCHITECTURAL_INVARIANTS.md` — this guide is the
operator-facing summary, not a replacement for either.

The platform is a **thin reasoning spine** (Understand → Reason → Ground → Contextualize → Plan →
Coordinate → Execute → Act → Observe → Validate → Recover → Reflect → Learn), governed throughout by
**Policy + Human Interaction + Approval Exchange**, measured by **Operations**, timed by the
**Scheduler**, all resting on a **Foundation**: an append-only, replayable Event Log that is the single
source of truth for everything.

Two facts every operator needs before anything else:

1. **The log is truth.** Nothing not recorded as an event happened. Every domain object you can query
   (a Goal, a Plan, an approval decision, a schedule) is a *projection* — a read derived by folding the
   event log, never an independent record. If you ever see a discrepancy between "what the system says
   happened" and "what's in the log," the log is right.
2. **v2 has a production entrypoint as of RC1.** `python -m nexus_scheduler` (registered as the
   `nexus-v2` console script) boots the full durable spine — pipeline + approval exchange +
   operations + scheduler — over a real SQLite file and ticks the Scheduler against the real wall
   clock until interrupted (see §3 and §7, and `docs/v2/RC1_PRODUCTIZATION_REPORT.md`). It authors
   no goals itself — registering a `SpineRequest`/schedule is still a caller concern via the same
   composition-root API (see §3). `python -m nexus` and the Docker image still launch v1 unchanged;
   the two entrypoints are independent processes with no shared startup logic.

---

## 2. Subsystem map

| Package | Capability (Constitution) | What it owns | Producer prefix |
|---|---|---|---|
| `nexus_core` | contracts, domain objects | the 18 frozen object schemas; the sync persistence *interfaces* (no implementation) | — |
| `nexus_infra` | Foundation | the durable/in-memory Event Store, Unit of Work, snapshots, Observability | — |
| `nexus_intent` | Understand | turns a raw request into a frozen `Intent`/`IntentAnalysis` | `intent.*` |
| `nexus_engineering` | Reason | Engineering Strategy (classification, approach, risk, autonomy proposal) | `engineering.*` |
| `nexus_estimation` | Reason (quantitative) | complexity/duration/cost/confidence estimates | `estimation.*` |
| `nexus_repository`, `nexus_operator`†, `nexus_history`, `nexus_research`† | Ground | facts-only grounding subsystems (repository facts, execution history) | `repository.*`, `execution_history.*` |
| `nexus_context` (+`grounding/`) | Contextualize | assembles the Context Package; grounding-aware relevance selection over Knowledge | `context.*` |
| `nexus_planning` (+`grounded/`) | Plan | decomposition, Work Packages, Execution Graph, resolved Skills | `plan.*`, `execution_graph.*`, `planning.*` |
| `nexus_orchestration` | Coordinate | scheduling/sequencing, runtime candidate discovery, pause/resume/cancel ownership | — |
| `nexus_harness`, `nexus_runtime`(+adapters) | Foundation / Runtime | the Harness Registry; runtime allocation and selection | `runtime.*` |
| `nexus_execution` (+`actuation/`) | Execute / Act | drives one runtime attempt; multi-wave graph traversal and dispatch | `execution.*` (see note below) |
| `nexus_validation` | Validate | completion verdicts from independently-verifiable Evidence | — |
| `nexus_recovery` | Recover | retry/escalate/resume decisions on failure | — |
| `nexus_reflection` | Reflect | deterministic aggregation → Knowledge Candidates | — |
| `nexus_knowledge` | Learn | governs acceptance of Knowledge; read-only serving to Reason/Contextualize/Plan | — |
| `nexus_policy` | Govern (sole evaluator) | the only component that ever constructs a policy verdict; fail-closed by default | `policy.*` |
| `nexus_human_interaction` | Govern (surface)‡ | the operator façade — submit/inspect/replay/restart/explain; delegates approvals | `interaction.*` |
| `nexus_approval` | Govern (approval lifecycle) | Requested→Pending→Approved\|Denied\|Expired, durably, for every gate | `approval.*` |
| `nexus_operations` | Operate | read-only platform observation (sessions, execution status, approval queues, health, diagnostics) | `operations.*` |
| `nexus_scheduler` | Foundation (timing) | *when* a Goal or platform operation begins; Policy-mediated autonomy | `scheduler.*` |
| `nexus_workflows/spine` | composition root | `ConstitutionalPipeline` — fuses every owner above into one Goal→Knowledge driver | `pipeline.*` |
| `nexus_integration` | (built, unwired) | the ADR-008 flag/shadow/correlation substrate — see §9, not in the live call graph today | `migration.*` |
| `nexus_briefings`, `nexus_operator`†, `nexus_research`† | consumer applications | real v2.0.0a1 code sitting *above* the spine, not part of the 13-capability model; currently unwired into any entrypoint | — |

† `nexus_operator` and `nexus_research` are legitimate top-level applications, not Grounding
subsystems — their names collide with Constitution concepts (an unbuilt "Operator Profile" grounding
subsystem; a "Research" capability that doesn't exist in the Constitution at all). See the P17 report
§1.6 before reading older docs that group them differently.

‡ `nexus_human_interaction`'s composition root (`build_human_interaction()`) is not wired into
`nexus_scheduler.bootstrap()` (the live v2 entrypoint) — it builds its own independent
`ConstitutionalPipeline`/`ApprovalExchange` pair. Real, tested code; the same "built, unwired" shape as
`nexus_integration` and the consumer applications below, currently reachable only via a caller that
constructs it directly (e.g. tests).

**Note on `execution.*` producer attribution:** Actuation's traversal events carry `producer="runtime"`
(they reuse the Runtime Engine's event builder) even though their type namespace is `execution.*`. This
is a known, harmless, already-tracked cosmetic nuance (P12 finding F-6) — lineage still reconstructs
losslessly; don't be surprised when `producer` and event-type prefix don't match for this one family.

---

## 3. Execution lifecycle — Goal to Knowledge

```
operator request
  -> Intent (nexus_intent)                       "what does the operator want?"
  -> Engineering Strategy (nexus_engineering)     "how should this proceed?" (+ Estimation)
  -> Context Package (nexus_context, grounding-aware over Knowledge)
  -> Execution Plan (nexus_planning/grounded)     Plan + Work Packages + Execution Graph + Skills
  -> Execution Actuation (nexus_execution/actuation)
       multi-wave traversal: for each ready node ->
         Orchestration offers runtime candidates -> Runtime Manager selects+dispatches
         -> Execution Engine drives one runtime attempt -> raw execution.*/runtime.* events
       an approval-gated node pauses (WAITING) here until the Approval Exchange grants it
  -> Validation (nexus_validation)                completion verdict from independent Evidence
  -> Recovery (nexus_recovery)                    continuation decision (complete/retry/escalate)
  -> Reflection (nexus_reflection)                Knowledge Candidates
  -> Knowledge (nexus_knowledge)                  governed acceptance into the durable learning graph
```

The whole chain is driven by exactly one coordinator you should ever call directly:
`nexus_workflows.spine.ConstitutionalPipeline.run(request, control=...)`, built via
`build_constitutional_pipeline(infrastructure, ...)`. Every stage above appends to the *same* event log
(`infrastructure.event_store`) under the same correlation, so the whole episode — from the first `intent.*`
event to the last `knowledge.*` event — replays and restarts as one unit (§4, §5).

**Approval gates.** A `WorkItemSpec(requires_approval=True)` becomes a `Constraint(kind="approval")` node
in the Execution Graph. Actuation leaves that node `WAITING` rather than failing; the run's
`SpineRun.execution_state.waiting_nodes` names it. Nothing resumes it automatically except the Approval
Exchange (§6) — Actuation itself never grants its own gates.

---

## 4. Replay model

**Replay is a pure, read-only fold over the event log.** Every `reconstruct_*`/rebuild path in the
platform (schedules, approval sessions, execution state, plans, strategies) takes `events:
tuple[Event, ...]` and returns a value object — it never writes back to the log, and calling it twice in
a row is guaranteed to return the same thing (proven directly in P17 §2.1 row 8: three consecutive full
replays, and a "read only the first two events" partial read, all reproduce identical projected state and
never change `event_store.global_length()`).

Practical rules for operators:
- **A replay never re-invokes an engine.** A recorded LLM/heuristic/clock output (INV-17) is stored
  verbatim in its event's payload; replaying an episode does not re-run reasoning, re-consult Policy, or
  re-execute a runtime. This is why replay is fast (Phase 3: ~155,000–164,000 events/sec) and why it is
  safe to run as often as you like, including just to inspect state.
- **Replay is idempotent under interruption.** If a process reading the log dies partway through folding
  events, the next attempt starts clean and reaches the same answer — there is no partial-replay state to
  clean up, because replay never persists anything of its own.
- **You get replay for free from every read.** `pipeline.history()`, `scheduler.schedules()`,
  `approval.session(id)`, `operations.*` — all of these *are* a replay call under the hood; there is no
  separate "run a replay" operation to remember to invoke.

---

## 5. Restart model

**Restart = reopen the durable file + let every consumer replay from scratch.**
`build_durable_infrastructure(db_path)` opens (or creates) a SQLite/WAL file and wires a fresh set of
engines over it — there is no persisted "session," no server process to reattach to. A restarted process
calls the exact same composition roots as a first boot; the durable log is the only thing that survived.

What restart guarantees (all directly tested in P17 §2.1 and pre-existing suites, not just claimed):
- **No lost committed writes, even across a hard process kill** — SQLite's WAL-mode atomic commit holds;
  an in-flight, uncommitted write at the moment of a crash simply never appears (§2.1 row 6).
- **No duplicate dispatch.** A scheduled occurrence, an approval decision, or an execution node already
  recorded before a restart is never re-run after one — every consumer keys off durable facts already in
  the log (`_FIRED` sets, `dispatched` tuples, `granted_gates`), not in-memory state.
- **Identical reconstructed state.** Every subsystem's restart test asserts genuine equality between the
  pre-restart and post-restart projections — not merely "the process didn't crash."
- **No migration path today.** The schema is `CREATE TABLE IF NOT EXISTS` only (no version tracking) —
  restarting against a file created by an older schema is untested and unsupported. See the P17 report's
  Release Readiness section before changing the schema of a file with real data in it.

Operationally: to restart a v2 process, just re-run whatever script called
`build_durable_infrastructure(same_path)` the first time. There is no `shutdown()` to call first (none
exists — see the P17 report §5) and none is required for correctness, though a deliberate WAL checkpoint
before a *planned* stop is good hygiene the platform does not currently automate.

---

## 6. Approval model

Owner: `nexus_approval.ApprovalExchange`, built via `build_approval_exchange(pipeline, infrastructure,
now=...)`. Lifecycle, one gate at a time: `Requested → Pending → Approved | Denied | Expired` — every
transition is a durable `approval.*` event, single producer, fully audited.

- **`publish(session_id, waiting_nodes)`** — called after a pipeline run leaves nodes `WAITING`; records
  `Requested`+`Pending` for each not-yet-published gate (idempotent — safe to call again).
- **`approve(request, node, decided_by=..., reason=...)`** — records the decision, then **resumes
  execution itself** by re-driving `ConstitutionalPipeline.run(request, control=SpineControl(granted_gates=...))`
  with the now-granted gate included. This is the only way a paused pipeline resumes past an approval
  gate.
- **`deny(session_id, node, ...)` / `expire(session_id, node, ...)`** — records a terminal, un-resuming
  decision; the gate stays un-authorized.
- **`sweep_expired(session_id, now=...)`** — expires every pending request past its `expires_at` deadline
  (ISO-8601 strings compare lexicographically, so this needs no date parsing).
- **`session`/`pending`/`history`/`explanation`** — read-only projections; `explanation` is the
  human-readable "why does this gate exist" surface, naming the taxonomy (`automatic` / `human_review` /
  `multi_stage` / `deferred`, from the Plan's own `ExecutionStrategy.approval_policy`) that required it.

`nexus_human_interaction` is the only sanctioned front door for a human — it never records an approval
decision itself; every method delegates to the Exchange above. **Known risk (P17 §1.2 R5):**
`AutonomyMode.FULLY_AUTOMATIC` schedules (§7) auto-approve *every* waiting gate once the top-level
`autonomous_execution` Policy check passes, regardless of that gate's own declared taxonomy — this is
tested, intentional P16 behavior, not a bug, but it means a `human_review`-tagged gate *will* be silently
auto-approved under a Fully-Automatic schedule. Choose autonomy modes with this in mind.

---

## 7. Scheduler model

Owner: `nexus_scheduler.Scheduler`, built via `build_scheduler(spine, approval, operations, now=...)`.
Owns exactly one thing: **when** a Goal (or a read-only platform operation) enters the pipeline — never
reasoning, execution, or governance itself.

- **Trigger kinds:** `immediate`, `one_time(run_at)`, `delayed(delay_seconds)`,
  `interval(interval_seconds, ...)`, `from_cron(alias)` (alias-level only — `@minutely`/`@hourly`/`@daily`/
  `@weekly`, no full crontab expressions).
- **`schedule_goal(identity=, request=, trigger=, autonomy=)`** registers a durable schedule; the
  `SpineRequest` itself is serialized onto the `scheduler.registered` event (`dump_spine_request`), so a
  restart doesn't need the caller to remember what was scheduled.
- **`tick(now)`** is the only thing that makes time pass — nothing fires on a wall clock inside the
  platform. An operator (or a host process's own scheduler — cron, a loop, a task queue) must call
  `tick(now)` periodically with the current time. Each call reconstructs every schedule from the log,
  finds occurrences due at `now` not already fired, and dispatches them via the Constitutional Pipeline
  only (never an engine directly).
- **Autonomy modes:** `MANUAL` (records a request; a human must run it), `GOVERNED` (auto-runs; gates
  pause for a human), `FULLY_AUTOMATIC` (auto-runs and auto-approves gates *only if Policy permits* — see
  §6's caveat).
- **`cancel`/`pause`/`resume`/`expire`** — durable lifecycle transitions on the schedule itself (distinct
  from execution's own pause/resume, which Orchestration owns).

**Scale ceiling fixed in RC1 (was P17 §3.2/§4.2 — the single most significant finding that program made):**
`tick()` used to be **quadratic** in the number of currently-registered schedules (~9.6 seconds at 1000
schedules), because its per-schedule completion check (`_maybe_complete`) re-fetched and re-reconstructed
*every* schedule from the full event history once per schedule in the outer loop. RC1 fixed this by
reusing the outer loop's already-reconstructed schedule plus the occurrence count it just fired, so
`_maybe_complete` no longer touches the event log at all. `tick()` is now linear in the number of
registered schedules (~10 ms at 1000, ~27 ms at 2000 — see `docs/v2/RC1_PRODUCTIZATION_REPORT.md` for the
full before/after benchmark). No behavior changed — same dispatch order, same completion semantics, same
replay/restart guarantees; only the internal cost changed.

---

## 8. Learning loop

Owner path: **Reflection → Knowledge Candidates → Knowledge (acceptance) → future Reason/Contextualize/Plan.**

1. After Recovery decides continuation, `nexus_reflection` deterministically aggregates the episode
   (what happened, why, patterns) into a `ReflectionReport` and proposes `KnowledgeCandidate`s — advisory
   only; Reflection never writes Knowledge itself (INV-25) and never calls Planning (INV-26).
2. `nexus_knowledge.KnowledgeEngine.ingest(candidate)` is the **only** path that can create a durable
   Knowledge item — it governs acceptance (accept/evolve/merge/reject) under a `PersistencePolicy`, and
   only evidence-backed candidates (referencing real Validation evidence) clear it (INV-24).
3. On a *later* episode, `nexus_context`'s grounding-aware assembly (`nexus_context/grounding`) reads
   accepted Knowledge (read-only, INV-06) and folds relevant items into that episode's Context Package —
   this is the loop closing: what was learned from one Goal becomes available context for a later one,
   never as a direct call, always through the durable Knowledge store.
4. `nexus_workflows/spine/learning.py`'s `KnowledgeSelector` plus the `knowledge_grounding` Policy
   allow-baseline gate this path — it is enabled by default in `build_constitutional_pipeline(...,
   learning=True)` and can be disabled per-call.

This loop is exercised end-to-end (Goal → Reflection → Knowledge → a *second* Goal's Context Package
picking it up) by `tests/integration/test_learning_loop.py` — the tests to read if you need to see it
proven rather than described.

---

## 9. Troubleshooting

| Symptom | Likely cause / where to look |
|---|---|
| A pipeline run I expected to complete is stuck `WAITING` | An approval gate is pending — check `approval.pending(session_id)`; nothing auto-resumes a `GOVERNED` schedule's gate |
| A restarted process re-ran something I thought was already done | Almost certainly a bug if reproducible — every consumer in this platform is designed to key off durable facts (open an issue against the specific subsystem); check first whether you reopened the *same* db file |
| A second goal on a shared durable log silently skipped its own Intent/Planning/Actuation, or two goals collided on validation/runtime events | Fixed in RC2 — restart-seeding and Runtime Session scoping previously keyed off a work-item id or "first fact in the log" rather than the goal actually being run; see `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`. Confirm you're running RC2-or-later code. |
| `scheduler.tick()` is taking multiple seconds | Fixed in RC1 (§7) — `tick()` is now linear; if you still see multi-second ticks, check you're running RC1-or-later code, not the pre-fix `nexus_scheduler/scheduler.py` |
| A `PolicyDecision`-shaped object appears somewhere unexpected | Should be structurally impossible outside `nexus_policy` — every consumer reads a verdict via `.simulate(...)`, never constructs one; treat this as a serious bug report |
| I can't find any log output | v2 had no logging before P17; pass `observability=LoggingObservability()` to your composition root and configure the `"nexus.infra"` logger (§10) |
| Two different `PolicyContext` classes show up in a stack trace | Harmless naming coincidence — `nexus_engineering.model.PolicyContext` (a read-only policy-verdict projection) vs. `nexus_policy.composition.PolicyContext` (the Policy composition-root bundle); different objects, not a bug |
| I reopened a durable file and got an error immediately | Confirm you're not pointing at a v1 database (`nexus/`) by mistake — the two strata never share a schema or a file; also confirm the file wasn't truncated by something outside the platform (SQLite/WAL recovers from a real crash, not from external corruption) |
| A `test_state_machines.py` failure appears in your own sweep | Pre-existing, unrelated to v2 — it needs a `db_session` fixture from v1's conftest, stripped when you run with `--noconftest`. Not a v2 regression. |

---

## 10. Operational tooling added by P17

- **`nexus_infra.LoggingObservability`** — a stdlib-`logging`-backed `Observability` implementation.
  Wire it into any composition root: `build_infrastructure(observability=LoggingObservability())` (or
  the durable equivalent). Configure the `"nexus.infra"` logger with your handler of choice; `WARNING`
  for conflicts/failures/dead-letters, `INFO` for everything else. See `nexus_infra/observability.py`.
- **`scripts/p17_benchmark.py`** — re-runnable performance measurement (startup, throughput, latency,
  memory) over the real composition roots. Run before/after any change you're worried might regress
  performance.
- **`scripts/p17_scale.py`** — re-runnable scale validation (concurrent sessions, many schedules, many
  approvals, large graphs, large Knowledge stores, replay/restart at a larger event count). Use it to
  re-check the scheduler ceiling (§7) after any future fix.
- **`tests/integration/test_p17_failure_resilience.py`** — genuine process-crash, replay-safety, and
  recovery-durability regression tests, runnable like any other test.
- **`tests/integration/test_harness_registry_unity.py`** — regression coverage for the INV-36 fix (§11).

---

## 11. Extension guide

Adding a new capability or consumer to v2 should follow the pattern every P0–P16 program used:

1. **One new package, one producer.** Give it its own `nexus_<name>/events.py` with a `_PRODUCER`
   constant unique repo-wide (`grep -rn "_PRODUCER = " nexus_*/` to check) and its own `<name>.*` event
   type namespace.
2. **Consult Policy, never evaluate it.** If your subsystem needs a governance decision, import
   `DecisionRequest` + an action-class constant + a data-only baseline function from `nexus_policy`, call
   `policy.simulate(...)`, and read `verdict.allowed`/`.decision`/`.reasoning_trace`. Never construct or
   import `PolicyDecision` outside `nexus_policy` itself — this is checked by
   `tests/unit/nexus_policy/test_guardrails.py::test_no_consumer_emits_a_policy_verdict`, a crude
   substring scan over every package's `.py` files (avoid the literal string `"PolicyDecision"` even in
   comments/docstrings).
3. **Reconstruct from the log, never hold authoritative in-memory state.** Every durable object should be
   a `ValueObject` projection built by a pure `reconstruct_*(events)` function, never a second frozen
   schema for something `contracts/*.md` already owns (INV-07).
4. **Determinism seam:** any non-deterministic input (clock, LLM output, random id) must be captured as
   event data, never recomputed on replay — inject a clock/`now` callable with a fixed test double, follow
   the `system_now()`-as-default-parameter pattern used throughout.
5. **Drive execution only through `ConstitutionalPipeline`**, never a downstream engine directly, if your
   subsystem needs to run a Goal (the pattern `nexus_scheduler.AutonomousExecutionCoordinator` uses).
6. **Wire it in a `composition.py`**, following the existing `build_<name>(infrastructure, ..., now=...) ->
   <Name>Context` shape, and add it to `pyproject.toml`'s `[tool.hatch.build.targets.wheel] packages` list
   plus **all three** CI gates in `.github/workflows/core-ci.yml` (ruff, mypy, pytest+coverage) — six
   packages currently skip this last step; don't add a seventh (see the P17 report's Release Readiness
   section).
7. **Write the guardrail tests, not just the behavior tests** — an architecture-fitness test (import scan
   for forbidden dependencies), a determinism test (no wall clock/randomness outside the seam), and a
   replay/restart test (reopen a durable file, assert identical reconstructed state) are the three every
   existing package has and every new one should too.
