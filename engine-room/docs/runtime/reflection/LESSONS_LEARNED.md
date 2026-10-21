# Lessons Learned — Reflection Engine

The objective: make Nexus deterministically analyse completed operational history and produce
immutable Reflection Reports that **explain system behaviour without modifying execution,
governance, or recovery** — the analytical layer that prepares structured insight for the
future Knowledge subsystem. **Achieved, with no architectural change.** No
`ARCHITECTURAL_CONFLICT_<N>.md` was produced.

---

## 1. Architectural assumptions confirmed

- **The frozen Reflection architecture (doc 26) is implementable as-is.** Its design principles,
  reflection questions, pattern-identification list, confidence levels, and boundaries mapped
  directly to code.
- **INV-25 is the right spine.** "Reflection produces Knowledge *Candidates*; Knowledge decides
  persistence" gave the layer a crisp remit: it reaches an *analytical output* and stops.
  Candidates travel inside the Report as advisory data — Reflection persists Reports and
  Patterns, never Knowledge.
- **INV-26 held cleanly.** Reflection depends on nothing upstream of it and is depended on by
  nothing; Planning never imports it. The `Reflection → Knowledge → Planning` path is a data
  flow, not a build edge.
- **The layer-output pattern generalises a fifth time.** The Reflection Report, Operational
  Pattern, and Knowledge Candidate are Reflection-owned value objects (no frozen core contract),
  exactly like the Runtime Session, Execution Result, Validation Report, and Recovery Plan. The
  pattern held without friction.
- **Reserved event namespaces + id markers scale to five layers.** `reflection.*` needed no new
  architectural event; the `refl-` id marker keeps reflection events collision-free alongside
  `runtime.*`, `-val-`, and `-rec-` in the shared, correlated store.
- **Determinism is achievable for an analytical layer.** Pure aggregation, first-seen grouping,
  count-derived confidence, and injected timestamps yield byte-identical reports and event
  streams — the program's headline requirement — with *no* statistical learning or AI.

## 2. Engineering refinements (not architecture)

- **Reflection analyses a *history*, not one execution.** This is the first layer whose input is
  a *window* of many operations. The `OperationalEpisode` (a read-only, by-reference projection
  correlated by session) is the unit the analyzers aggregate over — a clean way to consume three
  per-execution outputs at once without coupling to any of them.
- **Confidence: doc-26 canon, derived deterministically.** The prompt required "no AI, pure
  deterministic aggregation," and doc 26 fixes four confidence levels
  (Experimental/Observed/Validated/Proven). We mapped **repetition count → level**
  (`1 → Experimental … ≥5 → Proven`), which is explainable, reproducible, and honest about how
  much evidence backs a finding.
- **Candidates only from *confirmed, actionable* patterns.** doc 26 (*Actionable*):
  "observations without actionable insight should not become operational knowledge." So a
  Knowledge Candidate is emitted only from a pattern that both repeats (confirmed) and is of an
  actionable kind (repeated failure, bottleneck, retry frequency, repeated success). One-off
  findings are recorded as patterns but do not become candidates.
- **Analyzers assert only what the evidence supports.** Each returns *no pattern* when its
  dimension is absent (no failures, no duration samples, no friction), so the report never
  over-claims. The `ExecutionDurationAnalyzer` aggregates a `duration_ms` metric when present and
  is honestly silent when it is not — rather than inventing a proxy.
- **`reflection.completed` vs `reflection.failed`.** Mirrored the prior layers' convention:
  `failed` means there was *no operational history to analyse* (an empty window), not that the
  analysis process errored. Analyzers are total (never raise), so the process itself cannot fail;
  both paths still build and persist a Report.
- **Scope is an explicit input.** Because reflection spans many sessions, its ids derive from a
  caller-supplied **scope** (the operational window's identity) rather than a single session —
  consistent with Reflection being a pure function of the window it is given.

## 3. Future integration points for Knowledge

1. **Knowledge ingestion** — a Knowledge subsystem consumes `ReflectionReport.knowledge_candidates`
   (advisory) and decides what becomes persistent (INV-25). Reflection already emits candidates
   with confidence and source-pattern references for prioritisation.
2. **Richer analyses** — new `OperationalAnalyzer`s (context value, strategy effectiveness,
   capability utilisation — doc 26 categories) compose without an engine change.
3. **Cross-window reflection** — the current engine reflects one window; aggregating across
   windows (doc 26 *Future Evolution*) is a higher-level scope over persisted reports.
4. **Planning (indirect only)** — learning reaches Planning through persisted Knowledge, never
   directly from Reflection (INV-26). The separation is preserved end-to-end.

## 4. Success criteria — status

| Criterion | Result |
|---|---|
| Deterministically analyse completed history → immutable report | ✓ |
| Reflection consumes immutable history only; never modifies it | ✓ (read-only projection; doc 26 *Evidence First*) |
| Runtime / Execution / Validation / Recovery unchanged | ✓ (append-only + dependency guardrails) |
| Reflection Reports immutable; reference (not duplicate) artifacts | ✓ (INV-12) |
| Deterministic reports; identical history → identical reports | ✓ (determinism tests) |
| No AI, no learning, no Knowledge mutation | ✓ (pure aggregation; candidates only — INV-25) |
| ADRs / contracts / invariants unchanged | ✓ |
| Analytical layer prepared for the future Knowledge subsystem | ✓ |
