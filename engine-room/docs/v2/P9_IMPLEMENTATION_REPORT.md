# P9 Implementation Report — Context Engineering (the Contextualize capability)

- **Date:** 2026-07-16
- **Program:** P9 (Context Engineering) as briefed — the constitutional **Contextualize** capability
- **Governing decisions:** ARCHITECTURE_CONSTITUTION (capability #4 *Contextualize*; Article IV
  determinism seam; INV-01/02/06/07/13/14/17/27), the frozen `contracts/context_package.md`,
  `docs/v2/03_CONTEXT_ENGINEERING.md`, ADR-001 (event authority), ADR-004 (Policy sole evaluator),
  ADR-007 (durable persistence), ADR-008 (shadow-adjudicable)
- **Rule observed:** implementation only — no architecture redesign, no protocol/contract/invariant/
  ADR edits, no engine redesign, no commit. Two constitutional conflicts were **surfaced and
  adjudicated with the operator before any code** rather than silently reconciled (see §1, §2).

---

## 1. Executive Summary

Context Engineering is the constitutional **Contextualize** capability — the single owner of
execution-context assembly. It **already exists** as the incumbent `nexus_context` package (Phase 4):
1,348 LOC, 13 test files, wired into ~15 call sites, and the **only** producer of the frozen
`ContextPackage` (INV-02; `context_package.md` §2 — "the only producer of this object"). P9 therefore
did **not** create a second Context Engineering owner. It made the incumbent producer
**grounding-aware**: a new additive submodule, **`nexus_context/grounding/`**, that consumes the new
grounding/reasoning artifacts, performs deterministic **explainable relevance selection**, and feeds
the selected facts to the incumbent producer, which packages and persists the one Context Package (the
P9 "ExecutionContext").

**Two constitutional conflicts were discovered and adjudicated before implementation:**

- **The P9 brief says "Engineering Intelligence consumes ExecutionContext" and "Planning consumes
  EngineeringStrategy only."** Both invert the frozen spine. The Constitution orders **Reason (EI) →
  Contextualize (Context Engineering) → Plan**: EI runs *before* Context Engineering, reads grounding
  directly, and **emits** context objectives that Context Engineering *assembles*; the frozen
  `context_package.md` states the Context Package is **consumed by Planning**; and the already-merged
  P5 (`nexus_engineering`) and P6 (`nexus_planning/strategy_binding.py`) are built exactly this way
  (P5 report §9 adjudicated the identical point). Honouring the brief's inversion would require editing
  frozen contracts and merged code — forbidden by this task's own rules. **Resolution (operator-approved):
  build the constitutional order.** Context Engineering is the downstream Contextualize owner; the
  "ExecutionContext" **is** the frozen Context Package (one canonical schema — INV-07).

- **A second producer would violate INV-02/INV-07.** Context Engineering already owns the object.
  **Resolution (operator-approved): enhance the incumbent additively** — a `nexus_context.grounding`
  submodule, not a competing `nexus_context_engineering` package. Mirrors P8's additive-integration
  precedent; the incumbent, its 13 test files, and all ~15 call sites are untouched.

**New surface — `nexus_context/grounding/`** (5 modules + `__init__`): `model` (`GroundingInputs`,
`SelectionRecord`, `GroundingSelection`, `GroundedContextResult`), `selection` (`GroundingSelector` —
the deterministic, explainable selector), `collectors` (five grounding `ContextCollector`s),
`assembler` (`GroundingAssembler` + `context.grounding.*` facts + observability), `composition`
(`build_grounded_context_engineering`). **Packaging + persistence + the core `context.*` events are
delegated to the incumbent** (single producer). **No** engine, protocol, contract, or invariant was
changed; the incumbent `nexus_context` is byte-for-byte unmodified.

**Tests** — `tests/unit/nexus_context/grounding/` (4 files, 23 tests) + `tests/integration/
test_grounding_durable.py` (3 tests). **26 new tests, all green.** Full v2 sweep: **2617 passed**.
Ruff clean; MyPy strict clean (6 source files).

---

## 2. Constitutional Compliance

| Constitutional requirement | Status | How |
|---|---|---|
| Context Engineering is the **single owner** of context assembly (INV-02) | ✅ | The incumbent `nexus_context` remains the *only* producer of `ContextPackage`; grounding feeds it and produces no second object. Guardrail: grounding defines **no** `DomainObject` subclass. |
| **One canonical schema** for operational context (INV-07) | ✅ | The P9 "ExecutionContext" **is** the frozen `ContextPackage`; grounding introduces no alternative representation (guardrail-proven). |
| Contextualize **assembles**, never **reasons** (Article IV; Intelligence Model table) | ✅ | Selection is a pure function of recorded facts — deterministic heuristics only, no LLM, no embeddings, no semantic search, no floating-point score. |
| Contextualize **receives** the approach, never decides it | ✅ | The EngineeringStrategy's facets are surfaced as *context* (validation rigor → execution context, runtime prefs → resource context); grounding re-derives no approach. |
| **Consumes Knowledge read-only** (INV-06) | ✅ | Knowledge is surfaced by reference only (id + type + short summary); never embedded, never mutated. |
| Serves facts **by reference** (INV-27; INV-12) | ✅ | ADRs/contracts/modules/knowledge/prior-executions carried as references (`adr:…`, `knowledge:…`); the incumbent embeds no evidence. |
| **Reason once, emit once, replay forever** (INV-17) | ✅ | The selection is recorded in `context.grounding.selected`; the assembled package in `context.grounding.assembled`. Replay reconstructs both without re-selecting/re-assembling. |
| **Every inclusion and omission explainable** (P9 core) | ✅ | Every `SelectionRecord` (selected *and* omitted) carries why-selected/omitted, source, relationship, priority. Absent sources are explained too. |
| Event Log is truth; state is a projection (INV-13/14) | ✅ | Grounding writes only its own output through the reused P1 repository; the package is a projection of the log. |
| Dependency direction one-way (INV-01) | ✅ | `nexus_context.grounding → {nexus_context, nexus_core, nexus_infra}` + read-only upstream **model** imports (`nexus_engineering.model`, `nexus_history.model`, `nexus_repository.profile`, `nexus_intent.model`, `nexus_core.domain.knowledge`); imports **no** downstream engine (guardrail-proven). |
| No commit | ✅ | Nothing was committed. |

---

## 3. Context Assembly Architecture

The assembly pipeline runs the P9 stages and delegates packaging to the incumbent producer:

```
GroundingInputs (read-only, by value)              GroundingAssembler.assemble
  Goal ─────────────────┐                              │
  IntentAnalysis ───────┤   Intent Collection          │ 1. select()  → GroundingSelection
  RepositoryProfile ────┤   Repository Grounding        │              (deterministic, explainable)
  ExecutionHistoryProfile│  Historical Grounding         │ 2. emit context.grounding.selected  (INV-17)
  Knowledge (read-only) ─┤   Knowledge Grounding         │ 3. grounding_collectors(inputs, selection)
  EngineeringStrategy ───┘   Constraint/Resource/Exec    │ 4. incumbent ContextEngineeringService.engineer
      (context_objectives = the assembly directive)      │       collect → normalize → conflict → rank
                                                         │       → freshness → package → persist → emit
                                                         │ 5. emit context.grounding.assembled (replay anchor)
                                                         ▼
                                          GroundedContextResult(result, selection)
                                              └─ package = the one frozen ContextPackage
```

- **Immutable intermediate objects, no hidden mutation.** `GroundingInputs` (frozen), `GroundingSelection`
  / `SelectionRecord` (frozen value objects), and the incumbent's `ContextItem`/`RawContextFragment` are
  all immutable; each stage returns new values.
- **The selector never rescans or recomputes.** RepositoryProfile (P7), ExecutionHistoryProfile (P8),
  EngineeringStrategy (P5), and Knowledge are consumed **by value** — already-recorded facts. Grounding
  reconstructs none of them.
- **Single producer preserved.** The assembler constructs the incumbent `ContextEngineeringService` with
  the grounding collectors prepended by the incumbent's own defaults, so exactly one `ContextPackage` is
  produced, packaged, and persisted by the incumbent owner.

## 4. Selection Model

`GroundingSelector.select(inputs) -> GroundingSelection` — the deterministic, explainable core:

1. **Criteria.** The selection criteria are the **EngineeringStrategy's context objectives** (P5) when
   present, else keywords derived deterministically from the Goal (outcome, domain, in-scope items,
   success definition). Objectives and keywords are both recorded on the selection.
2. **Candidates.** Every artifact the RepositoryProfile / ExecutionHistoryProfile / Knowledge expose is a
   typed `_Candidate` with a base priority per kind and a stated relationship: ADRs, contracts,
   invariants, architecture docs, modules, packages, files, prior executions, knowledge items.
3. **Verdict.** A candidate is **selected** when its identity (repository artifacts) or its
   semantic relationship (knowledge / prior executions) matches a criterion keyword; knowledge, already
   relevance-filtered by its retrieval seam, is admitted by default. Everything else is **omitted with a
   reason**. Selected sets are then **capped per kind** (minimal-complete context — doc 03); overflow is
   omitted with an explicit rank reason. **Absent grounding sources** are recorded as explained omissions.

Every `SelectionRecord` carries the four required fields — **why selected/omitted** (`reason`),
**source**, **relationship**, **priority** — plus the `selected` verdict. There is **no LLM, no semantic
search, no embedding, and no floating-point score**; identical grounding yields an identical selection
and identical ordering (`test_selection_is_deterministic`).

## 5. Context Packaging

Packaging is **delegated to the incumbent** `ContextPackageBuilder` (the single producer). Grounding
threads its verdict into the package additively:

- Selected facts become the incumbent's `RawContextFragment`s across the eight canonical Context
  Categories (workspace/resource/execution/historical/operational/constraint), each carrying references
  (`adr:…`, `contract:…`, `module:…`, `knowledge:…`, `execution:…`) that surface in
  `ContextPackage.references`.
- Selected document-like artifacts (ADRs, contracts, invariants, architecture docs, knowledge, prior
  executions) are added to `ContextPackage.supporting_artifacts` as `Reference`s.
- Absent grounding sources become explained `ContextPackage.known_unknowns`
  (`grounding_gap:<source>:<reason>`).
- The full selection provenance — **including every omission with its reason** — is recorded in the
  `context.grounding.selected` event (the event log is the truth for omissions; the package carries the
  minimal-complete *selected* context).

The output is exactly **one immutable `ContextPackage`** per Goal (INV-07; one package per Goal).

## 6. Persistence

No new persistence. The incumbent persists the `ContextPackage` through the reused P1
`InMemoryRepository` (durable transparently over `build_durable_infrastructure`, ADR-007). Grounding
adds only two `context.grounding.*` facts through the infrastructure emitter — the same substrate,
correlated to the Goal. Grounding writes no store it reads from.

## 7. Replay Validation

`tests/integration/test_grounding_durable.py`:

- **Durable + correlated** (`test_grounding_facts_are_durable_and_correlated`): after assembly, a reopened
  durable infrastructure contains exactly `context.grounding.selected` + `context.grounding.assembled`,
  both correlated to the Goal.
- **Replay without rebuilding** (`test_replay_reconstructs_context_without_rebuilding`): reconstructing
  `ContextPackage.model_validate(assembled.payload["package"])` and
  `GroundingSelection.model_validate(selected.payload)` from the reopened log yields objects **value-equal**
  to the originals — no re-selection, no re-assembly. (Two JSON-safety fixes were required so the package
  round-trips through the log — a `Domain` enum and a tuple were coerced to primitives in fragment
  payloads.)

## 8. Restart Validation

`test_restart_reconstruction_is_identical`: assembling the same `GroundingInputs` over a fresh set of
engines wired on the **reopened** SQLite file reproduces a **byte-identical** `ContextPackage` and an
identical `GroundingSelection`. The package carries no timestamp (per the frozen contract), so its
determinism is independent of the clock; the selection is a pure function of the recorded facts.

## 9. Integration Points

- **Consumes (read-only, by value):** `nexus_core.domain.{Goal, Knowledge}`, `nexus_intent.model.
  IntentAnalysis`, `nexus_repository.profile.RepositoryProfile`, `nexus_history.model.
  ExecutionHistoryProfile`, `nexus_engineering.model.EngineeringStrategy` (its `context_objectives`
  facet is the assembly directive), and the P1 `InfrastructureContext`. It imports upstream **model**
  modules only — never an upstream engine, never a downstream engine (guardrail-proven).
- **Produces:** the incumbent's one `ContextPackage` per Goal, plus two `context.grounding.*` facts.
  `build_grounded_context_engineering(infrastructure)` is the single new DI seam.
- **Downstream unchanged:** Planning still consumes the `ContextPackage` (its canonical input) and the
  Engineering Strategy (posture hints via the merged `strategy_binding`) — exactly as P6 built it. No
  engine was changed; the guardrail proves grounding imports no downstream engine.
- **Constitutional flow preserved:** Intent Resolution → Goal; Engineering Intelligence → Engineering
  Strategy (with context objectives); Repository Intelligence → RepositoryProfile; Execution History →
  ExecutionHistoryProfile; Knowledge → read-only query; **Context Engineering assembles** → one Context
  Package → Planning.

## 10. Risks

| Risk | Severity | Note / mitigation |
|---|---|---|
| Keyword-substring selection is coarse vs. semantic relevance | Medium | Deterministic and explainable by construction (no LLM permitted here). The criteria are the EngineeringStrategy's context objectives when present; the selector is a clean seam an operator can extend with richer deterministic rules. Every verdict is auditable, so coarseness is visible, never silent. |
| Generic goal words could over-select | Low | Repository artifacts match on **identity** only (not their generic relationship label); knowledge/prior-executions match on their semantic relationship. Per-kind caps bound the selected set (minimal-complete context). |
| Grounding provenance for omissions lives in the event, not the frozen package | Low | Intentional: the frozen `ContextPackage` schema is not extended (INV-07). Omissions are recorded facts in `context.grounding.selected` (replayable); genuine gaps (absent sources) surface in the package's `known_unknowns`. |
| Absence of any grounding source | Low | Fully absence-tolerant: only the Goal is required; each absent source degrades to an explained omission and the incumbent still produces a valid package. |
| Program-label divergence (this "P9" vs. the engineering program's P9 = Operations) | None | Sequencing, not conflict — same divergence noted in the P4/P5/P7/P8 reports. The authoritative record is the implementation reports; this P9 = Context Engineering. |

**Two genuine constitutional conflicts were discovered and resolved with the operator** (not silently
reconciled): the EI-consumes-context inversion (rejected in favour of the frozen spine) and the
second-producer collision (resolved by enhancing the incumbent additively). Both are documented in §1.

## 11. Remaining Work Before P10

Context Engineering now assembles a grounded Context Package deterministically and explainably from all
upstream grounding/reasoning artifacts. Outstanding, none blocking:

1. **Wire the grounded assembler into the running spine:** connect Intent Resolution → Engineering
   Intelligence → **grounded Context Engineering** → Planning end-to-end (a composition/cutover step, on
   P10's path). The incumbent's existing call sites continue to work unchanged in the meantime.
2. **Richer deterministic selection (optional):** dependency-graph proximity (module edges), ADR/contract
   cross-reference following, and freshness-weighted history — all deterministic, all additive behind the
   existing `GroundingSelector` seam.
3. **Freeze nothing new:** the "ExecutionContext" is the already-frozen Context Package; no contract
   freeze is required (INV-07 discipline preserved).

**Verdict:** P9 is functionally complete. Context Engineering remains the single constitutional owner of
context assembly; it now consumes RepositoryProfile (facts only), ExecutionHistoryProfile (facts only),
Knowledge (read-only), and the EngineeringStrategy's context objectives, selects deterministically and
explainably, and produces exactly one immutable Context Package that replays and reconstructs identically
after restart — with no redesign and no change to any engine, protocol, contract, or invariant. **No
commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_context/grounding` unit (`test_selection`, `test_collectors`, `test_assembler`, `test_guardrails`) | **23 passed** |
| `tests/integration/test_grounding_durable.py` (durable / replay / restart) | **3 passed** |
| Incumbent `nexus_context` suite (regression) | **green, unchanged** |
| Full v2 `nexus_*` unit + key integration sweep | **2617 passed** |
| MyPy strict on `nexus_context/grounding` | **Success: no issues found in 6 source files** |
| Ruff check + format on new files | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent
> here); the v1-app tests (`scheduling`, `config`, `health`, `state_machines`, …) need the v1
> `db_session`/settings fixtures and are outside the v2 sweep — exactly as in the P1–P8 reports.
