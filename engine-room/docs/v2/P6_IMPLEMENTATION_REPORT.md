# P6 Implementation Report — Intent Resolution & Planning Integration

- **Date:** 2026-07-14
- **Program:** P6 (Intent Resolution + Planning Integration) as briefed — the constitutional **Understand** capability, and moving engineering ownership out of Planning
- **Governing decisions:** ARCHITECTURE_CONSTITUTION (capability 1 Understand; Article IV determinism seam), frozen `contracts/intent.md` + `contracts/goal.md`, the `docs/v2/engineering/03` "EI adds a producer, not a mutation" compatibility property, ADR-001 (event authority / determinism), ADR-004 (Policy sole evaluator), ADR-007 (durable log), ADR-008 (shadow-adjudicable)
- **Rule observed:** implementation only — no redesign, **no Planning rewrite** (additive integration only), no protocol/contract/invariant/ADR edits, no commit.

---

## 1. Executive Summary

P6 completes the constitutional reasoning flow **Intent → Intent Resolution → Engineering Intelligence → Planning** and moves engineering ownership out of Planning.

**`nexus_intent`** is the constitutional **Intent Resolution** subsystem — the single owner of *understanding operator intent* (INV-02). Given a raw operator request it **understands** and produces an immutable `IntentAnalysis`: the **frozen** `Intent` (the one canonical schema — INV-07), a `Goal` when resolved, the emitted `ClarificationRequest`s, extracted operator preferences, and an `IntentConfidence` assessment. It determines *what* the operator wants and **never decides how** — no estimation, execution reasoning, runtime/skill selection, policy, orchestration, execution, validation, recovery, or reflection (each proven by an import-level guardrail). Ambiguity never silently propagates: a below-confidence request emits clarifications and produces **no** Goal ("clarification preferred over incorrect execution"). Clarifications are *emitted* (recorded in the resolution fact), **not** handled — Human Interaction is a later program.

**Planning integration is additive — Planning becomes a pure decomposition engine.** Planning now **consumes** the `EngineeringStrategy` (the Constitution permits "Plan may depend on the Engineering Strategy") instead of deriving engineering postures. Concretely: EI's facets (execution style, autonomy, recovery, validation rigor, runtime capabilities) are translated by a new `bind_strategy` seam onto Planning's existing input surface — the optional posture hints on `PlanningRequest` that `StrategyAssigner` **already** prefers over its own derivation (the `coordination_hint` pattern, extended). **The decomposition algorithm is untouched.** With a Strategy present, Planning no longer derives those postures; absent one, the existing operator-authored derivation applies as a backward-compatible fallback — every prior Planning test passes unchanged. Planning still owns, and only owns, work breakdown, dependency graph, execution graph, package construction, and sequencing.

**Determinism (INV-17): understand once, emit once, replay forever.** The interpreter is a pluggable `Interpreter` protocol (an LLM interpreter attaches behind it); the default `DeterministicInterpreter` performs genuine multi-signal understanding (objective/domain/constraint/preference extraction, ambiguity + missing-information detection, clarification generation, confidence). The engine records **one** `intent.resolved` fact embedding the analysis; replay reconstructs the understanding — including clarifications — without re-understanding. Durability is transparent through P1 (ADR-007).

**No engine was rewritten; no protocol, contract, or invariant was changed.**
- **New package — `nexus_intent/`** (10 modules): `model`, `interpreter` (seam + default), `engine`, `events`, `ids`, `observability`, `persistence`, `composition`, `__init__`.
- **Additive Planning changes** (no algorithm change): optional posture fields on `PlanningRequest`; `StrategyAssigner` prefers those hints (same pattern it already used for `coordination_hint`); a new `nexus_planning/strategy_binding.py` (the EI-facets → Planning-postures seam); an optional `engineering_strategy=` parameter on `PlanningService.plan`.
- **Changed — `pyproject.toml`** (added `nexus_intent`) and **one guardrail**: `nexus_planning` was removed from the P5 EI "must-not-reason" list (it is now a *sanctioned consumer* of the Strategy), its consume-but-never-reason boundary proven in a new P6 guardrail.

**Tests** — `tests/unit/nexus_intent/` (5 files + fixtures), `tests/unit/nexus_planning/test_p6_ownership.py`, `tests/integration/test_p6_flow.py`.

> **Program-label note (sequencing, not a conflict).** The Engineering Program numbers Intent Resolution as **P7**. This task briefs it as **P6**, after Engineering Intelligence (task-P5) so the full Understand→Reason→Plan flow can be closed in one program. Same label/sequencing divergence noted in P4/P5; not a constitutional conflict — Understand is capability 1 on the spine and the Constitution's own migration order is "Intent Resolution → Engineering Intelligence → Planning," which this program realizes.

---

## 2. Constitutional Compliance

| Requirement | Status | How |
|---|---|---|
| Intent Resolution is the **single owner of understanding intent** (INV-02) | ✅ | Only `nexus_intent` produces the `Intent`/`Goal` from a request; guardrail proves it imports no decision engine. |
| Understand determines **what, never how** | ✅ | No estimation/execution-reasoning/runtime/skill/policy/orchestrate/execute/validate/recover/reflect — import guardrail over all of them. |
| Uses the **frozen `Intent` schema** (INV-07) | ✅ | `nexus_intent.model` imports `nexus_core.domain.Intent`; `IntentAnalysis` *bundles* the frozen Intent + Goal (no competing representation); `ClarificationRequest` types the Intent's open `clarification_requests` Struct. Proven by guardrail. |
| Ambiguity never silently propagates | ✅ | Below-confidence request → `interaction_required`, clarifications emitted, **no Goal** (AwaitingClarification); a Goal is produced only when resolved. |
| Clarifications **emitted, not handled** | ✅ | `ClarificationRequest`s are recorded in the `intent.resolved` fact; no Human Interaction wired. |
| Planning becomes a **pure decomposition engine** | ✅ | Planning consumes EI's postures via `bind_strategy`; it derives them only as a fallback for operator-authored requests; it owns breakdown/graph/packages/sequencing exactly as before. |
| Planning **consumes `EngineeringStrategy`** (not reasons) | ✅ | `plan(goal, request, engineering_strategy=…)` binds the Strategy's facets onto Planning's inputs; guardrail proves Planning references the Strategy *value* but never `EngineeringIntelligence`/the reasoner. |
| Planning performs **no** engineering reasoning / estimation / policy eval / runtime recommendation | ✅ | Four source guardrails (`test_p6_ownership.py`). |
| Each owner owns **exactly one** responsibility | ✅ | Intent ≠ planning; EI ≠ planning; Planning ≠ reasoning/estimation/policy — all guardrail-proven. |
| Determinism seam (INV-17) | ✅ | Interpreter understands once; one `intent.resolved` fact; replay reconstructs without re-understanding. |

**Constitutional move, precisely.** The Constitution's object model already says EI's Strategy carries the postures and that "the engines' input contracts are unchanged; only the *source* of the declaration moves from human to platform." P6 realizes exactly that: `StrategyAssigner` already treated `coordination_hint` as an override of its derivation; P6 extends that override to the remaining postures and adds the EI→Planning translation. Ownership moved; no algorithm was redesigned.

---

## 3. ADR Compliance

- **ADR-001 (event authority / determinism):** the `IntentAnalysis` is recorded as one `intent.resolved` event; the stored analysis is a projection; the one captured-as-data value is the injected event timestamp (INV-17), never used in interpretation. Planning's events are unchanged.
- **ADR-004 (Policy sole evaluator):** Intent Resolution evaluates no governance (it "identifies intent only; it does not enforce governance" — `intent.md` §7); Planning still evaluates no policy. Approval *posture* now flows from EI (which queried Policy via `simulate`), and Policy still decides the outcome (INV-29).
- **ADR-007 (durable persistence):** no subsystem-specific durable code — Intent Resolution emits through the `InfrastructureContext` and persists analyses through a reused `InMemoryRepository`; over `build_durable_infrastructure` both are durable and the analysis reconstructs from the log after restart. Planning rides its existing durable path.
- **ADR-008 (shadow migration):** untouched. Both the default interpreter and `plan(..., persist=False)`-style resolution are deterministic and side-effect-free, so Intent Resolution is directly shadow-adjudicable via P3 (probabilistic class if an LLM interpreter is later injected).

---

## 4. Intent Resolution Architecture

```
IntentRequest (raw request, modality, correlation)
        │
        ▼   ┌──────────────────────────────┐
            │ Interpreter (pluggable seam)  │  understand once
            │ default = Deterministic       │  (objective, domain, constraints,
            │ (multi-signal understanding)  │   preferences, ambiguity, missing,
        ▼   └──────────────────────────────┘   clarifications, confidence)
   IntentResolution.resolve
        │ emit once
        ▼
   intent.resolved  (durable, correlated; embeds the IntentAnalysis)
        │ replay forever
        ▼
   IntentAnalysis = { frozen Intent, Goal | None, ClarificationRequest[], IntentConfidence,
                      operator_preferences, resolved, interaction_required }
        │  (Goal only when resolved — "clarification preferred over incorrect execution")
        ▼
   Goal ──► Engineering Intelligence ──► EngineeringStrategy ──► Planning
```

- **Understanding, not lookup.** The default interpreter weighs multiple signals per facet and records evidence + confidence: objective extraction (imperative-prefix normalization), domain detection (weighted keyword sets), constraint extraction (prohibition/restriction/limit markers), preference extraction, ambiguity detection (vague terms, underspecification), missing-information detection, deterministic clarification generation, and a factored confidence assessment. An LLM interpreter attaches behind the same `Interpreter` protocol and records identically, so replay stays deterministic per INV-17.

---

## 5. Planning Integration

**The seam (`nexus_planning/strategy_binding.py`).** `bind_strategy(request, strategy)` maps EI facets → Planning postures and returns a copied request; `StrategyAssigner` prefers these over derivation:

| EngineeringStrategy facet | → Planning posture (ExecutionStrategy) |
|---|---|
| `execution_style` (sequential/parallel/mixed) | `coordination` (SEQUENTIAL/PARALLEL/HYBRID) |
| `autonomy_level` (autonomous/…/manual) | `approval_policy` (AUTOMATIC/HUMAN_REVIEW/MULTI_STAGE) |
| `recovery_posture` | `retry_policy` + `recovery_policy` |
| `validation_rigor` (+ evidence classes) | `validation_policy` |
| `runtime_preferences` (capabilities) | `runtime_policy` (capabilities, not providers — INV-37) |
| `identity` | `engineering_strategy_ref` (provenance) |

**What did *not* change:** the decomposition (`ExplicitDecompositionStrategy`), work-package generation, execution-graph construction, capability resolution, plan building, validation, and every event — untouched. The only edits are (a) optional fields on `PlanningRequest` (a subsystem value object, not a frozen contract), (b) `StrategyAssigner` reading those hints with the existing prefer-hint-else-derive pattern, and (c) an optional `engineering_strategy=` parameter on `plan`. The operator-authored path (no Strategy) is byte-for-byte the prior behavior — proven by the unchanged Planning suite and `test_operator_authored_path_still_works_without_a_strategy`.

---

## 6. Determinism Validation

- **Identical request → identical analysis** (`test_determinism.py::test_identical_request_produces_identical_analysis`): value-equal analysis + identical content-addressed identity.
- **Analysis reconstructs from serialized form**, and over the durable log **intent analysis replays without re-understanding** (`test_p6_flow.py::test_intent_analysis_replays_from_the_log`).
- **Clarification replay** (`test_clarification_replay_is_deterministic`): clarifications are deterministic and survive the serialization round-trip.
- **Planning replay + restart determinism** (`test_p6_flow.py::test_restart_determinism_reproduces_intent_and_plan`): a fresh set of engines over the reopened SQLite file reproduces the same intent identity, strategy identity, plan identity, and Execution Strategy.
- **Planning consumes EngineeringStrategy** (`test_planning_consumes_engineering_strategy`): the Plan's Execution Strategy carries EI's rigor and runtime capabilities.
- **No randomness / no clock in understanding** (`test_guardrails.py`): AST-level import check; `datetime` only in `events.py`.

---

## 7. Explainability

Every analysis is explainable: the frozen Intent carries `detected_intent`, `detected_domain`, `ambiguity`, `missing_information`, `clarification_requests`, `priority_estimate`, and `interpretation_rationale`; the `IntentConfidence` carries a level + score + factors; each `ClarificationRequest` carries a subject, question, and reason. The resolution `reasoning_trace` records the interpretation path. Downstream, the Plan's `engineering_strategy_ref` records which Strategy authored its postures, so the whole chain — request → understanding → strategy → plan — is auditable and replayable end to end.

---

## 8. Integration Points

- **Intent Resolution consumes:** a raw `IntentRequest`; **produces:** `IntentAnalysis` (frozen `Intent` + `Goal`), `ClarificationRequest`s, `IntentConfidence`. `build_intent(infrastructure)` is the single DI seam. It imports only `nexus_core` + `nexus_infra`.
- **Planning consumes:** the `Goal` (Intent Resolution's output, as before) **and** the `EngineeringStrategy` (new). `nexus_planning → {nexus_core, nexus_infra, nexus_engineering}` — the one added dependency, constitutionally sanctioned ("Plan may depend on the Engineering Strategy"). It imports `nexus_engineering.model` only (the Strategy value), never the reasoner/engine.
- **The completed flow:** `IntentResolution.resolve` → `EngineeringIntelligence.strategize_for_goal` → `PlanningService.plan(goal, request, engineering_strategy=…)` — demonstrated end-to-end and durably in `test_p6_flow.py`.

---

## 9. Risks

| Risk | Severity | Note / mitigation |
|---|---|---|
| Deterministic interpreter is coarse vs. an LLM interpreter | Medium | Pluggable seam; an LLM interpreter attaches behind `Interpreter` and records identically (INV-17). The default is auditable, self-contained, and the correct foundation before the cognitive layer. |
| Planning now imports `nexus_engineering` | Low | Constitutionally sanctioned (Plan may depend on the Engineering Strategy); one-way (EI never imports Planning — guardrail); no cycle. Planning consumes the value only, never the reasoner. |
| Multi-round clarification loop not implemented | Low (by design) | P6 emits clarification requests; the interactive Received→AwaitingClarification↔Interpreting→Resolved loop is Human Interaction's concern (a later program). The single-pass resolution records one fact; the frozen Intent's lifecycle states remain available. Documented. |
| Operator-authored Planning path must stay intact | Low | Additive prefer-hint-else-derive; the entire prior Planning suite passes unchanged, plus an explicit backward-compat test. |
| `IntentAnalysis` duplicates some Intent fields (clarifications typed + as Struct) | Low | The frozen Intent needs open Structs; the analysis exposes the typed form. This is the sanctioned "type the open Struct" pattern (as P2 did for policy conditions); no schema competes. |

**No constitutional conflict was discovered.** Two places pressed against the brief and were surfaced rather than silently reconciled: (a) the task names the output "IntentAnalysis," but the canonical schema is the **frozen `Intent`** (INV-07) — so `IntentAnalysis` is a *bundle* of the frozen Intent + Goal + clarifications (the `PlanningResult` pattern), not a competing representation; (b) "additive integration only / do not rewrite Planning" was honored by extending Planning's **existing** override mechanism (`coordination_hint`) rather than changing any decomposition algorithm — the operator-authored path is preserved as fallback, and the P5 guardrail was *refined* (Planning is now a sanctioned Strategy consumer), not deleted.

---

## 10. Remaining Work Before P7

The Understand→Reason→Plan flow is closed and replayable. Outstanding, none blocking:

1. **Human Interaction (the clarification loop):** reach the operator with the emitted `ClarificationRequest`s and feed responses back into a new resolution round (the Intent lifecycle's AwaitingClarification↔Interpreting). P6 emits; a later program handles.
2. **LLM interpreter / reasoner (optional):** inject behind the `Interpreter`/`Reasoner` protocols when a reasoning runtime seam exists; records identically, shadow-adjudicable via P3.
3. **Wire the flow into Orchestration/Execution:** the `PlanningResult` (now carrying EI's postures) feeds Coordinate→Execute; the first governed end-to-end cutover is a later program (P10-equivalent).
4. **Freeze `engineering_strategy`/intent-analysis shapes** if/when a second consumer needs them (INV-07 discipline) — deferred, not precluded.

**Verdict:** P6 is functionally complete. Intent Resolution is the single owner of understanding operator intent; Planning is a pure decomposition engine that consumes the `EngineeringStrategy` instead of producing engineering reasoning; clarification requests are emitted but not handled; replay reconstructs both the intent analysis and the plan without re-understanding or re-reasoning; existing engines are unchanged except for additive integration; and no protocol, contract, or invariant was changed. **No commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_intent` unit + Planning P6 ownership + P6 flow integration | **186 passed** |
| Full v2 `nexus_*` unit + integration sweep (incl. modified Planning) | **2569 passed**, 1 skipped |
| Lint (`ruff`) on new package + Planning changes + tests | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent here) — a pre-existing environment condition; the v1-app tests need the v1 `db_session`/settings fixtures and are outside the v2 sweep, exactly as in the P1–P5 reports.
