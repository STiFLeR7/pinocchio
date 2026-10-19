# P8 — Execution History (Grounding Layer) — Implementation Report

**Status:** Complete. No commit made (standing rule).
**Package:** `nexus_history/` (12 modules) · **Tests:** 21 unit + 4 integration (25 new) · **Sweep:** 2730 passed, 1 skipped (opt-in), ruff clean.
**Program-label note:** the Constitutional Engineering Program numbers this Grounding subsystem inside the Grounding family (P4 band); the task sequence calls it *P8*. Sequencing after the reasoning spine lets EI consume it immediately. No architecture was redesigned.

---

## Executive Summary

Execution History is now the **single constitutional owner of historical operational facts** (Constitution, Grounding plane; INV-02). Given a `HistoryQuery` the `ExecutionHistory` engine **reconstructs history once** from the authoritative event log and produces **one immutable, facts-only** `ExecutionHistoryProfile`, records **one** `execution_history.projected` fact embedding it (INV-17), and replay reconstructs the identical view without re-projecting.

It answers "what happened before?" — previous executions, execution timeline, runtime history, runtime-selection history, validation/recovery/reflection history, knowledge lineage, historical artifacts and evidence, execution frequency, goal/work-package/operator/repository history — **all reconstructed from durable persisted state**. It **never reasons, never summarizes with AI, never recommends**. The profile carries no recommendations, no scoring, no confidence, no reasoning — only historical facts (counts, timelines, references, lineage edges).

The subsystem is a **grounding leaf**: it imports only the foundation (`nexus_core`, `nexus_infra`). It reads the operational log read-only and emits **only** `execution_history.*` events. Repository Intelligence consumes history through its existing seam; Engineering Intelligence consumes historical facts — both by value, neither queries the log itself, and Execution History imports neither.

---

## Constitutional Compliance (verified from source, not prose)

| Requirement | How it holds | Proof |
|---|---|---|
| Single owner of historical facts (INV-02) | Only `nexus_history` constructs `ExecutionHistoryProfile` / emits `execution_history.*` | `test_only_history_owns_historical_facts` |
| Retrieves only — never classifies/estimates/reasons/plans/executes/recovers/validates/reflects/decides policy | Package imports only `nexus_core`/`nexus_infra`/itself; no LLM/random; constructs no `EngineeringStrategy`/`PolicyDecision`/`EstimationReport`/`RecoveryPlan` | `test_history_is_a_grounding_leaf`, `test_history_never_reasons_or_decides` |
| Facts only (no recommendation/scoring/confidence/reasoning) | Every facet is a count/timeline/reference/lineage-edge `ValueObject`; no score or confidence field exists on the profile | `model.py`; `test_projection_reconstructs_operational_facets` |
| Never summarizes with AI | No `openai`/`anthropic`/`random` import anywhere | `test_history_never_reasons_or_decides` |
| Emits `execution_history.*` only; never modifies `runtime./validation./recovery./reflection./knowledge.*` | `events.py` defines exactly one type, `execution_history.projected`; the projection **reads** the operational families, never emits them | `test_history_emits_only_execution_history_events` |
| History reconstructed from authoritative events, **never duplicated** | The engine reads `event_store.read_all()`; persistence stores only its own profile, never a copy of the operational log | `persistence.py`; `retrieval.filter_events` |
| Determinism / replay / restart (INV-16/17) | Profile identity = content hash of facts (volatile excluded); projection excludes its own `execution_history.*` facts → idempotent | `test_projection_is_deterministic`, `_excludes_own_history_events`, durable suite |
| Repository Intelligence performs no historical reconstruction | RI imports no `nexus_history`; contains no `read_all`/`read_stream` | `test_repository_performs_no_historical_reconstruction` |
| Engineering Intelligence performs no historical lookup itself | EI imports no `nexus_history`; contains no `read_all`/`read_stream` | `test_engineering_performs_no_historical_lookup` |
| Constitution / ADR-001/004/007/008 / all invariants / frozen contracts | Unchanged. No contract, protocol, or invariant edited; `execution_history` view is a subsystem `ValueObject`, not a frozen core contract (INV-07 discipline) | diff is purely additive |

**Grounding non-responsibilities (Constitution §GROUND):** grounding "never plans, decides, or executes… serves facts by reference (INV-27), then stops." The profile serves references (artifact/evidence/work-package/knowledge ids), not embedded content, and terminates at facts.

---

## Historical Model

One immutable artifact — `ExecutionHistoryProfile` — a pure function of the operational log for a query scope. Facets map one-to-one onto the task's fifteen retrieval responsibilities:

| Responsibility | Facet |
|---|---|
| previous executions | `executions: tuple[ExecutionEpisode]` (per-correlation roll-up) |
| execution timeline | `timeline: tuple[TimelineEntry]` (ordered, windowed for large logs) |
| runtime history | `runtime: RuntimeHistory` (lifecycle counts + runtimes seen) |
| runtime selection history | `runtime.selections` (allocations + `orchestration.runtime_request_created`) |
| validation history | `validation: ValidationHistory` (counts + recorded verdicts) |
| recovery history | `recovery: RecoveryHistory` (counts + recorded decisions) |
| reflection history | `reflection: ReflectionHistory` (counts + correlations) |
| knowledge lineage | `knowledge_lineage: KnowledgeLineage` (counts + derivation edges) |
| historical artifacts | `artifacts: ArtifactHistory` (count + references) |
| historical evidence | `evidence: EvidenceHistory` (count + references) |
| execution frequency | `frequency: EventFrequency` (by-type + by-producer counts) |
| goal history | `goals: GoalHistory` (distinct operations/goals) |
| work package history | `work_packages: WorkPackageHistory` |
| operator execution history | `operators: OperatorHistory` (per-operator counts) |
| repository execution history | `repositories: RepositoryExecutionHistory` (per-repository counts) |

`HistoryQuery` scopes deterministically by `correlation_identifier`, `goal_identifier`, `repository_root`, `runtime`, or `operator` (empty query = the whole log). Scoping **selects by recorded facts, never reasons**.

---

## Projection Architecture

```
event_store.read_all()  ──►  retrieval.filter_events(events, query)   [scope + exclude execution_history.*]
                                          │
                                          ▼
                              projection.project(...)   ──►  ExecutionHistoryProfile (draft, id="")
                                 ├─ timeline.build_timeline        (ordered, windowed)
                                 ├─ lineage.build_lineage          (knowledge.* edges)
                                 └─ single-pass facet accumulation (counts + references, sorted)
                                          │
                                          ▼
                              engine._finish  ──►  identity = ids.profile_id(scope, facts)
                                          │
                                          ▼
                              engine._record  ──►  one execution_history.projected fact (INV-17)  +  own-store persist
```

**The determinism linchpin.** `retrieval.filter_events` excludes the subsystem's own `execution_history.*` facts. So emitting a projection never perturbs a later projection over the same operational log — the two views are identical, produce the same identity, hence the same event id, which the store treats as an idempotent no-op (INV-16). This is what makes "never duplicate history" and "replay produces identical views" simultaneously true. Modules `retrieval` / `projection` / `timeline` / `lineage` are pure functions of `(events, query)`; the engine adds only identity, persistence, and one event.

**Bounded embedding.** The timeline is windowed to its most recent `TIMELINE_LIMIT` (2000) entries, recorded via `timeline_truncated` — deterministic, and it keeps the embedded profile bounded on long histories. *(ponytail ceiling: fixed tail window; add position-range paging if head history is needed.)*

---

## Replay Validation

`test_replay_reconstructs_view_without_reprojecting` (durable): seed an operational episode, project once (emit the fact), reopen the SQLite-backed infrastructure, read the `execution_history.projected` event, and `ExecutionHistoryProfile.model_validate(event.payload["profile"])` **equals** the original — reconstructed from the log with **no re-projection**. `test_projection_is_deterministic` proves identical events → identical profile; `test_projection_excludes_own_history_events` proves a prior projection fact in the log does not change a fresh projection.

## Restart Validation

`test_restart_reconstruction_is_identical` (durable): seed, then build two independent `ExecutionHistory` engines over two fresh `build_durable_infrastructure(db)` opens of the same database; both project `persist=False`; the two profile identities are equal — restart reconstructs an identical historical view from the durable log. `test_history_event_is_durable_and_correlated` proves the fact survives reopen and carries its correlation.

---

## Integration Points (additive only)

1. **Repository Intelligence consumes history through its existing seam.** `RepositoryIntelligence.profile()` gains an optional `repository_history=` parameter (duck-typed). When supplied, RI maps its `available`/`prior_executions` into the *existing* `RepositoryProfile.execution_history` seam via `_history_seam`. RI **imports no `nexus_history`** and reconstructs nothing. The seam remains excluded from RI's identity (`_VOLATILE`), so a given tree yields the same identity regardless of history — proven by `test_repository_intelligence_consumes_history_through_its_seam` (grounded `available`/`prior_executions` correct; grounded identity == ungrounded identity). `ExecutionHistoryProfile.repository_seam()` supplies the read-only view.

2. **Engineering Intelligence consumes historical facts.** `strategize_for_goal()` gains `execution_history_profile=` (duck-typed) → `profile.as_facts()` folded into a new optional `ReasoningInputs.execution_history` field. `normalized()` adds the history key **only when present**, so every existing strategy identity is byte-for-byte unchanged (zero regression) while a history-grounded strategy differs — proven by `test_engineering_intelligence_consumes_historical_facts` (grounded identity != ungrounded). EI **imports no `nexus_history`** and never queries the log.

3. **Composition.** `build_history(infrastructure, *, now=…)` wires the reader to `infrastructure.event_store` (read-only) and the emitter to the infrastructure context — reusing the P1/ADR-007 substrate unchanged, transparent over `build_durable_infrastructure`.

*(Planning never queries history — confirmed: `nexus_planning` imports no `nexus_history`, per the leaf/ownership guardrails. Context Engineering will consume historical facts later; the `as_facts()` seam is ready.)*

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Self-referential feedback (projecting over own projection facts) breaks idempotency | High | `retrieval.filter_events` excludes `execution_history.*`; regression-proven by two tests | 
| Payload-key drift in operational subsystems weakens reference extraction | Medium | Facets are **count-first** (always correct); references use defensive `first(...)` over a candidate key set and degrade to event id, never crash |
| Large logs bloat the embedded profile | Medium | Timeline windowed (`TIMELINE_LIMIT`, `timeline_truncated`); ceiling documented with upgrade path |
| Repository/operator scoping is thin where the log lacks `root`/`operator` payload keys | Low | Facts-only and honest: empty when absent; `HistoryQuery` scopes what the log records |
| Duck-typed RI/EI seams accept malformed objects | Low | `getattr(..., default)` / `.as_facts()` contract; both integrations covered by durable tests |

---

## Remaining Work Before Context Engineering

- **Context Engineering consumption.** Context Engineering (Contextualize) should consume `ExecutionHistoryProfile.as_facts()` as historical grounding, exactly as EI now does — the seam exists; the wiring is a one-line additive param on Context's collection step (out of P8 scope).
- **Richer repository/operator scoping** once operational events carry `root`/`operator` in payloads (or via a correlation→repository index) — additive to `retrieval`, no model change.
- **Contract freeze.** If a second consumer needs the shape, freeze an `execution_history` contract (INV-07 discipline: freeze only when a second subsystem depends on it — EI + RI now both consume, so this is the next candidate for a P0-style freeze).
- **No blockers.** Execution History is durable, deterministic, replay/restart-validated, and consumed by two grounding clients today.

---

## Validation Summary

- **25 new tests** — `tests/unit/nexus_history/` (projection, retrieval, lineage, engine, guardrails) + `tests/integration/test_history_durable.py` (durable, replay, restart, RI-consumes, EI-consumes) — all pass.
- **Full v2 sweep: 2730 passed, 1 skipped** (opt-in Claude CLI smoke). **Ruff clean.**
- **No engine rewritten, no protocol/contract/invariant edited, no commit made.**
