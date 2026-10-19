# Reflection Engine — implementation

Milestones 1-5. The Reflection Engine is the **analytical layer** over completed operational
history (doc 26). It consumes the immutable outputs of the pipeline and produces an immutable
**Reflection Report** that *explains* system behaviour. It **never changes it**: it never
executes, retries, plans, mutates policy, updates Knowledge, or invokes AI (doc 26 boundaries;
INV-25 — it produces Knowledge *Candidates*, never persistent Knowledge; INV-26 — Planning
never depends directly on it). No architectural conflict was found; no
`ARCHITECTURAL_CONFLICT_<N>.md` was produced.

---

## 1. Position & inputs

```
Execution Results ─┐
Validation Reports ─┼─▶ Reflection Engine.reflect(scope, *, execution_results, validation_reports,
Recovery Plans ─────┘                              recovery_plans, events, metrics) ─▶ Reflection Report
```

Reflection is the first layer to analyse a **history** — a *window* of many completed
operations — rather than one execution. Inputs:

- **`ExecutionResult`s / `ValidationReport`s / `RecoveryPlan`s** — the immutable per-execution
  outputs of Execution / Validation / Recovery, correlated by session.
- **Runtime events** — carried through for provenance.
- **Operational metrics** — an optional window-level `Struct`.
- **`scope`** — the stable identity of the operational window (drives deterministic ids).

Reflection reads these and writes **only** its own outputs (the Report + Patterns) plus
`reflection.*` events. It never modifies the collected data (doc 26 *Evidence First*).

## 2. What `reflect` does (deterministic pipeline)

1. **collect** the inputs into an immutable, correlated `OperationalHistory` (`collector.py`,
   Milestone 1) and emit `reflection.started`;
2. run the deterministic **analyzers** (`analyzers.py`, Milestone 2), emit
   `reflection.analysis_completed`;
3. **synthesise** summaries, confidence, confirmed observations, and Knowledge Candidates
   (`synthesis.py`) and build the immutable **Reflection Report** (`report.py`, Milestone 3),
   emit `reflection.report_created`;
4. emit `reflection.completed` (history reflected) or `reflection.failed` (no operational
   history — nothing to reflect on) (Milestone 4);
5. **persist** the Report + Patterns and return the Report (Milestone 5).

## 3. Modules

| Module | Responsibility |
|---|---|
| `vocabulary.py` | closed enums (`ConfidenceLevel`, `ReflectionStage`, `PatternKind`) + `Reference` target-type strings |
| `ids.py` | deterministic `report_id` / `pattern_id` / `candidate_id` / `event_id` (`refl-` marker) |
| `episode.py` | `OperationalEpisode` — the correlated, read-only per-operation projection |
| `collector.py` | `ReflectionCollector` → `OperationalHistory` (join by session, first-seen order) |
| `analyzers.py` | `AnalysisContext` + eight deterministic analyzers + `DEFAULT_ANALYZERS` |
| `patterns.py` | `OperationalPattern`, `KnowledgeCandidate`, `confidence_for` |
| `synthesis.py` | `ReflectionSynthesizer` → `ReflectionInsight` (summaries, confidence, candidates) |
| `report.py` | `ReflectionReport` (immutable, reference-only output) |
| `events.py` | `reflection.*` taxonomy + `build_event` |
| `observability.py` | derived counters over the Phase 2 sink |
| `persistence.py` | `ReflectionRepositories` (reports + patterns) over the Phase 2 `InMemoryRepository` |
| `engine.py` | `ReflectionEngine.reflect(...)` orchestration |
| `composition.py` | `build_reflection(infrastructure, ...)` DI wiring |

Dependency direction: `nexus_reflection → {nexus_recovery, nexus_validation, nexus_execution,
nexus_runtime, nexus_core, nexus_infra}` — strictly downstream. Reflection does **not** depend
on Knowledge or Planning (INV-26): candidates travel *inside* the Report as advisory data.

## 4. Determinism

Every field of the report and every event id is a pure function of the collected history and
the injected timestamp — no clock, no randomness, no learning. Grouping preserves first-seen
order over the (already deterministic) episode sequence, so identical history yields a
byte-identical report and event stream (`test_engine.py::
test_two_runs_produce_identical_reports_and_events`; the E2E determinism test).

## 5. Tests & coverage

`tests/unit/nexus_reflection/` (collector, analyzers, synthesis, engine, units) +
`tests/integration/test_reflection_pipeline.py` — **57 tests, 100% branch coverage** on the
package. The full suite (2297 passed / 1 skipped) is green with all prior phases unchanged.
