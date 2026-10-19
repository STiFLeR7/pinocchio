# Phase 4 — Context Engineering Layer: Implementation Decisions

**Status:** Implemented. **Scope:** the context-engineering layer (`nexus_context/`).
**Authority:** This document records *implementation decisions* only. It does not
amend any ADR, contract, or invariant — the architecture remains frozen.
Observations that might warrant future architecture review are listed in §5 with
recommendations, not applied.

Context Engineering converts a validated Goal plus available operational information
into a single, immutable, deterministic **Context Package** (the frozen
`nexus_core` domain object), persists it through Phase 2 infrastructure, and emits
context events. It produces *understanding*; it never performs work. With Phase 4,
the operational-intelligence pipeline becomes:

```
Goal → Context Engineering → Context Package → Planning → Work Packages → Execution Graph → Execution Strategy
```

---

## 1. Component → architecture mapping

| Component (`nexus_context/…`) | Produces / does | Contract / Invariants |
|---|---|---|
| `service.ContextEngineeringService` | orchestrates the pipeline, persists, emits | doc 03 boundaries |
| `collectors` | raw fragments from source classes (Protocol + reference impls) | doc 03 *Context Sources* |
| `normalizer.Normalizer` | canonical `ContextItem` set | doc 03 *Collect* |
| `conflict_detector.ConflictDetector` | surfaced conflicts (never resolved) | doc 03 *Context Validation* |
| `relevance.RelevanceRanker` | deterministic relevance ordering | doc 03 *Minimal Complete Context* |
| `freshness.FreshnessValidator` | valid/stale/expired verdicts | doc 03 *Context Validation* |
| `builder.ContextPackageBuilder` | `ContextPackage` (immutable, 8 categories) | `context_package.md`, INV-06/07/12 |
| `validators` | fail-fast guards + conflict surfacing | doc 03 |
| `composition` | DI wiring over `nexus_infra` | — |

## 2. Key implementation decisions

1. **Deterministic, AI-free context.** Phase 4 forbids AI. Raw context arrives as
   explicit `RawContextFragment` values surfaced by injected collectors; the policies
   for relevance and freshness arrive on an immutable `ContextRequest`. Every
   identifier is a pure function of the Goal identity and the inputs' stable handles
   (`ids.py`), so identical inputs yield byte-identical Context Packages, items,
   conflicts, and event streams. The `ContextCollector` Protocol is the seam where a
   future real source collector (Git, Drive, calendar, knowledge base, …) plugs in;
   only deterministic, I/O-free reference collectors ship now.

2. **Collectors are provider interfaces (INV-independent, DI).** Phase 4 implements
   the *interface* and two reference collectors — `GoalContextCollector` (derives
   goal/domain context purely from the Goal) and `RequestFragmentCollector` (surfaces
   the request's explicit fragments) — plus `StaticContextCollector` for explicit
   wiring. No Git, no filesystem scanning, no network, no AI.

3. **Surface conflicts, never resolve them.** The detector reports duplicate,
   contradictory, stale (explicit supersession), and missing-dependency conflicts and
   the builder surfaces them in `known_unknowns` / `validation_status`. Nothing is
   silently merged or dropped — fail-fast for *malformed* input, surfacing for
   *conflicting* input.

4. **Deterministic relevance and freshness.** Relevance is explicit integer rules
   (category base + source weight + request-supplied additive overrides) — no LLM, no
   float heuristic. Freshness is measured against an **explicit** evaluation instant
   on the policy (never the wall clock), so verdicts are reproducible; an item with no
   timestamp or no applicable threshold is left unknown/valid rather than guessed.

5. **Reuse of the Phase 2 persistence mechanism.** The Context Package repository is
   an instance of the same Phase 2 `InMemoryRepository` generic; the emitter is the
   infrastructure context. No new persistence mechanism was created and `nexus_infra`
   was not modified.

6. **Injected, deterministic event timestamps.** Emitted events carry a timestamp
   from an injected `TimestampSource` (fixed in tests). The produced *domain object*
   carries no timestamp, so it stays deterministic regardless of the clock (INV-17).

7. **Planning integration by composition (no coupling).** The package is fed to
   Planning as `PlanningRequest.context_ref` via the `context_reference` helper
   (`target_type="context_package"`, matching the reference Planning already expects).
   Neither layer imports the other; the `Goal → Context → Package → Planning` pipeline
   is wired at composition time and proven by `test_integration.py`.

## 3. What was deliberately NOT built (out of scope)

AI reasoning, prompt engineering, Orchestration, Runtime/Harness selection, Skill
execution, Recovery, Knowledge updates, Reflection, scheduling, and APIs. Real source
collectors (Git, Drive, etc.) are later work behind the shipped `ContextCollector`
seam. Context Engineering's output is the input to Planning; it consumes the
infrastructure without modifying it.

## 4. Validation gate (all met)

| Gate criterion | Result |
|---|---|
| Context collected | ✅ via injected collectors |
| Context normalized | ✅ canonical, sorted `ContextItem` set |
| Conflicts detected | ✅ duplicate/contradiction/stale/missing-dependency, surfaced |
| Freshness validated | ✅ valid/stale/expired via explicit instant + policy |
| Immutable Context Package created | ✅ frozen `nexus_core.ContextPackage`, 8 categories |
| Events emitted | ✅ started/collected/validated/package_created/completed, failed-on-error |
| Persistence works | ✅ via Phase 2 repository |
| Existing phases remain green | ✅ 193 + 180 + 149 unchanged |
| No architectural invariant violated | ✅ no ADR/contract/`nexus_core`/`nexus_infra` change |

Coverage: `nexus_context` ~99.7% (branch), ≥95 floor. Full suite: 677 tests,
`mypy --strict` clean, `ruff` clean.

## 5. Design observations (for future architectural review — NOT applied)

- **O-4 (resolved at the seam).** Phase 3 recorded that `WorkPackage.context` was a
  placeholder pending Context Engineering. Phase 4 now produces real Context Packages,
  and `context_reference(package)` yields the `context_ref` Planning consumes. The
  planner's internal default placeholder (`context-{goal}`) remains untouched (frozen
  Phase 3 code); callers wire the real reference at composition time. No action needed.

- **O-5 — Context Package versioning / continuous enrichment is single-pass.** The
  contract (§3, §8) describes Ready → Enriching → Ready re-versioning. Phase 4 builds
  one initial version per cycle (`package_version`, default `"1"`) and leaves
  `enrichment_history` empty; lifecycle `status` is left unset (a projection of the
  event log, optional until projected). *Recommendation:* a future enrichment pass
  should emit the Enriching/Validating transitions and append `enrichment_history`;
  the by-version model is already in place. Low urgency.

- **O-6 — Concrete collectors have no home yet (mirrors O-3).** Real source collectors
  (repository, Drive, calendar, knowledge base) implement the shipped
  `ContextCollector` Protocol but require I/O adapters that belong to a later phase.
  Phase 4 ships only deterministic reference collectors. *Recommendation:* a future
  Collectors/Adapters phase owns the concrete, I/O-bound implementations; Context
  Engineering consumes them by injection. Low urgency.

Neither observation blocks Phase 4 or requires action now.
