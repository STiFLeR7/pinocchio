# P5 Implementation Report — Engineering Intelligence (the Reason capability)

- **Date:** 2026-07-14
- **Program:** P5 (Engineering Intelligence) as briefed — the constitutional **Reason** capability
- **Governing decisions:** ARCHITECTURE_CONSTITUTION (Article IV — reasoning lives only in Understand, Reason, Estimation, and always emits an immutable recorded decision), the `docs/v2/engineering/` design corpus (`01`–`04` input/output/strategy model), ADR-001 (event authority / determinism), ADR-004 (Policy is the sole evaluator; determinism boundaries), ADR-007 (durable log), ADR-008 (shadow-adjudicable)
- **Rule observed:** implementation only — no redesign, no protocol/contract/invariant/ADR edits, no engine redesign, no commit.

---

## 1. Executive Summary

`nexus_engineering` is the constitutional **Engineering Intelligence** subsystem — the single owner of *engineering reasoning* (Constitution Article IV; INV-02). Given immutable, read-only inputs it **reasons** and produces **exactly one** immutable, explainable artifact: the **`EngineeringStrategy`** — one coherent, declarative decision about *how work should proceed*. It reasons; it never executes.

EI consumes only what the input model (`engineering/02`) permits, all **by value / read-only**: the **Goal** (Intent Resolution's output), the **Estimation Report** (Estimation *feeds* EI), the **Policy ceiling** (from the sole evaluator — INV-28), **Knowledge**, **Repository Understanding**, **Operator Preferences**, and **Environment Facts**. It produces the Strategy's facets — **work classification, engineering objective, approach/strategy type, complexity class, execution style, context objectives, recommended runtime capabilities, recommended skills, validation rigor, coordination intent, recovery posture, autonomy/approval recommendations, risk assessment, observability requirements**, plus overall rationale and confidence. Nothing else.

**It reasons through the determinism seam (INV-17): reason once, emit once, replay forever.** The reasoner is a **pluggable `Reasoner` protocol** — an LLM-backed reasoner attaches behind it ("reason freely") — and the constitutional default `DeterministicReasoner` performs genuine multi-signal engineering inference (it is *not* a routing table: every facet weighs several signals, records the evidence that drove it, and carries a confidence). Whichever reasoner runs, the engine records **one** `engineering.strategized` fact embedding the Strategy; replay reconstructs the decision without re-inference. Durability is transparent through P1 (ADR-007).

**No engine, protocol, contract, or invariant was changed.** Integration is additive DI (`build_engineering`). EI **never executes, plans, schedules, selects a runtime, resolves a Skill, evaluates policy, estimates quantitatively, validates, recovers, or persists Knowledge** — each proven by an import-level guardrail. It *proposes* gates; Policy decides (INV-29). It *consumes* Estimation and Policy; it delegates to their owners and owns neither (INV-02).

**New package — `nexus_engineering/`** (10 modules): `vocabulary`, `model` (`EngineeringStrategy` + `Recommendation` + `PolicyContext` + `ReasoningInputs`), `reasoner` (the `Reasoner` seam + `DeterministicReasoner` inference), `engine` (`EngineeringIntelligence`), `events`, `ids`, `observability`, `persistence`, `composition` (`build_engineering`), `__init__`.

**Changed — `pyproject.toml`** (package list) and **two guardrails** that legitimately flip at P5: the P4 estimation guardrail `test_engineering_intelligence_does_not_yet_exist` became `test_estimation_does_not_depend_on_engineering_intelligence` (EI now exists as a *downstream consumer* of estimation; the leaf must not import it back), and `nexus_engineering` was added to the P2 policy guardrail's consumer list (proving EI *queries* the Policy Engine but never *evaluates*).

**Tests** — `tests/unit/nexus_engineering/` (6 files + fixtures) + `tests/integration/test_engineering_durable.py`.

> **Program-label note (sequencing, not a conflict).** The Engineering Program numbers Engineering Intelligence as **P8** (its "P5" is Human Interaction) and folds Estimation into P8. This task briefs EI as **P5**, after the Estimation Foundation (task-P4) it depends on. This is the same label/sequencing divergence noted in the P4 report, not a constitutional conflict: the Constitution places Reason (EI) immediately after Understand on the spine and states "EI mathematically needs Estimation," so building Estimation then EI is exactly the intended order. Reported here rather than silently reconciled.

---

## 2. Constitutional Compliance

| Constitutional requirement | Status | How |
|---|---|---|
| EI is the **single owner of engineering reasoning** (Article III/IV, INV-02) | ✅ | Only `nexus_engineering` constructs `EngineeringStrategy`/reasons; guardrail proves Planning/Runtime/Policy/Estimation/Orchestration/Validation/Recovery/Reflection/Knowledge neither import EI nor construct its Strategy. |
| Reasons freely, then **commits to the record** (Article IV, INV-17) | ✅ | The reasoner runs once; the engine emits one `engineering.strategized` fact embedding the Strategy; replay reads the record, never re-reasons. |
| Produces **exactly one** artifact — the Engineering Strategy (`03`) | ✅ | `strategize()` returns one `EngineeringStrategy`; no side-channel, no direct downstream call. |
| Consumes only the canonical inputs, **read-only / by value** (`02`) | ✅ | `ReasoningInputs` carries Goal + Estimation + Policy ceiling + Knowledge + Repository Understanding + Preferences + Environment; EI mutates none and imports no downstream engine. |
| **Intent-bearing, not instruction-bearing** (`03`) | ✅ | Facets are capabilities/preferences/envelopes: no runtime named (INV-32/37), no Skill resolved (INV-33), no Plan written (INV-03), no completion verdict (INV-20). |
| **Never executes / authorizes** (Article I, INV-29) | ✅ | EI proposes approval gates; Policy decides. Guardrail: no downstream-engine import; no `PolicyDecision`. |
| **Never estimates quantitatively** | ✅ | EI *consumes* the `EstimationReport` (complexity band, confidence, cost) as an influence; guardrail proves it imports none of Estimation's scoring modules. |
| Policy is a **ceiling, fail-closed** (INV-28/30) | ✅ | Autonomy ≤ policy ceiling; with no Policy Context, autonomy caps at *gated* and routes to an approval gate (fail-closed). |
| **Explainable** output (INV-31) | ✅ | Every facet carries reasoning chain, contributing evidence, assumptions, confidence, and its policy/estimation/knowledge influences. |
| **Absence-tolerant** grounding (`02`) | ✅ | Missing Estimation/Policy/Knowledge/Repository/Preferences degrade to conservative defaults with recorded assumptions, never fail. |
| Strategy is a subsystem value object, not a new frozen contract (INV-07) | ✅ | `engineering_strategy` is *Proposed*, not frozen (no `contracts/engineering_strategy.md`); the Strategy is a `ValueObject` (the `ValidationReport`/estimation pattern) — no contract was frozen or edited. |

**Coherence rules enforced (`engineering/04`).** The reasoner builds the Strategy coherent-by-construction and records the checks: *Autonomy ≤ what Policy permits* (autonomy is derived from risk then capped at the policy ceiling — a real cap, exercised by test), *Validation Rigor ≥ Risk floor* (rigor is a monotone function of risk, floored higher for release/migration), and *Runtime Preferences ⊆ available capabilities* (preferred capabilities are intersected with Environment Facts, dropped-and-noted when unavailable — INV-36).

---

## 3. ADR Compliance

- **ADR-001 (event authority / determinism):** the Strategy is recorded as an `engineering.strategized` event; the stored Strategy is a projection; the one captured-as-data value is the injected event timestamp (INV-17), never used in the reasoning.
- **ADR-004 (Policy sole evaluator; determinism boundaries):** EI never evaluates governance — it queries the Policy Engine via **side-effect-free `simulate`** for the ceiling and projects the result into a read-only `PolicyContext`. EI sits on the reasoning side of ADR-004's boundary (Reason *may* reason, recorded); the deterministic default keeps the whole decision replayable.
- **ADR-007 (durable persistence):** no EI-specific durable code — the engine emits through the `InfrastructureContext` and persists the Strategy through a reused `InMemoryRepository`; over `build_durable_infrastructure` both are durable and the Strategy reconstructs from the log after restart.
- **ADR-008 (shadow migration):** untouched. Because the default reasoner is deterministic and `strategize(..., persist=False)` is side-effect-free, EI is directly shadow-adjudicable via P3 when it migrates (a probabilistic determinism class if an LLM reasoner is later injected).

---

## 4. Reasoning Architecture

```
ReasoningInputs (immutable, read-only)                         EngineeringStrategy (immutable, INV-17)
  Goal ─────────────┐                                            ├─ classification      (evidence-weighed)
  EstimationReport ─┤                                            ├─ approach / strategy type
  PolicyContext ────┤     ┌───────────────────────────┐         ├─ complexity class     ← Estimation band
  Knowledge ────────┼────►│  Reasoner (pluggable seam) │────────►├─ execution style
  Repo Understanding┤     │  default = Deterministic   │         ├─ context objectives   → Context Eng.
  Preferences ──────┤     │  (multi-signal inference)  │         ├─ skill requirements    → Skill Selection
  Environment ──────┘     └───────────────────────────┘         ├─ runtime preferences   → Orchestration
                                     │ reason once                ├─ validation rigor      → Validation
                                     ▼                            ├─ coordination intent   → Execution Strategy
                        EngineeringIntelligence.strategize        ├─ recovery posture      → Recovery
                                     │ emit once                   ├─ autonomy / approvals  → Governance   ← Policy ceiling
                        engineering.strategized (durable, correlated)  ├─ risk assessment
                                     │ replay forever              ├─ observability
                                     ▼                            └─ rationale + confidence + coherence notes
                        model_validate(payload["strategy"]) == Strategy
```

- **The determinism seam.** `Reasoner` is a `Protocol`; the reasoning *strategy* is injectable. The default `DeterministicReasoner` (`version="1"`, recorded on every Strategy) performs genuine inference — classification weighs outcome-text signals + domain nudges (with recorded evidence and a confidence, defaulting to `generic` with a stated assumption when no signal exists); risk composes a per-classification base with irreversibility/priority/complexity escalators and reversibility de-escalators; approach, rigor, recovery, autonomy, runtime, skills, observability each synthesize from classification + risk + the consumed estimation/policy/knowledge. An LLM-backed reasoner is the "reason freely" path behind the same protocol; it records identically, so replay stays deterministic per INV-17. (This mirrors Estimation's deferred recorded-reasoning layer: the seam is real, not a stub.)
- **Consumption without ownership.** `EngineeringContext.strategize_for_goal` is where EI consumes its upstream owners: it calls the **Estimation Engine** for the report (Estimation records its own `estimation.estimated` fact and owns it) and the **Policy Engine's `simulate`** for the ceiling (no `policy.evaluated` fact — EI records no governance decision). EI records only the estimation *identity* and the policy *context projection* inside its own Strategy event, so its replay reconstructs from its own fact.

---

## 5. Determinism Validation

- **Identical inputs → identical Strategy** (`test_determinism.py::test_identical_inputs_produce_identical_strategy`): value-equal Strategy and identical content-addressed identity.
- **Strategy reconstructs from its serialized form** (`test_strategy_reconstructs_from_its_serialized_form`) and, over the durable log, **replay reconstructs it without re-inference** (`test_engineering_durable.py::test_replay_reconstructs_the_strategy_from_the_log`).
- **Restart determinism** (`test_identical_strategy_across_restart`): a fresh set of engines over the reopened SQLite file reasons to the value-equal Strategy identity.
- **No randomness / no clock in reasoning** (`test_guardrails.py`): AST-level import check proves no `random`/`openai`/`anthropic`/downstream-engine import; `datetime` is imported **only** by `events.py`, never by the reasoning.
- **Influence preservation** (`test_determinism.py`): the **estimation** reference + complexity influence, the **policy** ceiling + autonomy influence, and the **knowledge** references + approach influence are all preserved on the replayed Strategy.

---

## 6. Explainability

Every facet is a `Recommendation` satisfying the constitution's required shape (`test_engine.py::test_every_facet_carries_the_required_explainability_shape`): a **selection** (intent-bearing value(s)), a **reasoning chain**, **contributing evidence**, **assumptions**, a **confidence** in `[0,1]`, and its **policy / estimation / knowledge influences**. Worked example (the reference bug request):

```
classification:   bug_fix        evidence: matched {bug, failing, fix}; chain: highest-scoring
approach:         investigate_first   (bug + elevated risk)
complexity_class: <band>         estimation_influences: complexity estimate <id>, confidence <v>
risk_assessment:  high           evidence: irreversibility signals {production, partner} → raised
validation_rigor: high + [reproduction fixed, regression suite green, no unrelated diff]  (rigor ≥ risk floor, INV-20)
autonomy_level:   manual/gated   policy_influences: policy decision = <d>; chain: policy ceiling → cap
recovery_posture: checkpoint_and_escalate
runtime_prefs:    [code-generation, filesystem, version-control, high-context]  (capabilities, not providers)
rationale + confidence + coherence notes recorded
```

The whole Strategy is auditable end-to-end and replays exactly.

---

## 7. Integration Points

- **Consumes:** `nexus_core.domain.{Goal, Knowledge}`, `nexus_estimation` (`EstimationEngine`, `EstimationReport`), `nexus_policy` (`DecisionRequest` + the engine's `simulate`), and the P1 `InfrastructureContext`. All upstream/foundational — EI is downstream of these leaves and imports **no** downstream engine.
- **Produces:** one `EngineeringStrategy` per Goal; `build_engineering(infrastructure)` is the single new DI seam.
- **Does not yet wire Planning.** Planning will consume `EngineeringStrategy` in place of operator-authored strategy at its input boundary (the design's "EI adds a producer, not a mutation" compatibility property — `engineering/03`). No engine was changed in P5; the guardrail proves Planning does not reason. Wiring Planning to consume the Strategy is the P6/cutover step.
- **Dependency direction (INV-01):** `nexus_engineering → {nexus_core, nexus_infra, nexus_estimation, nexus_policy}` only — proven by the import guardrail.

---

## 8. Operational Impact

- **First reasoning capability online.** With Understand (Intent Resolution) still a prototype, EI is the first *engineering-reasoning* owner: given a Goal it emits a governed, explainable, replayable Strategy. Paired with Intent Resolution it completes "Nexus thinks."
- **Storage:** rides the infrastructure context — in-memory by default, one SQLite file when durable. No new stores.
- **Observability:** derived counters (`engineering.strategized`, `engineering.classification.*`, `engineering.autonomy.*`, `engineering.risk.*`) over the existing sink; never authoritative.
- **Default posture:** fail-closed autonomy — without a Policy Context, EI caps autonomy at *gated* and inserts an approval gate; with a policy that denies or requires approval, it proposes a manual/approval gate. EI never authorizes; it surfaces the gate for Policy/Human Interaction.

---

## 9. Risks

| Risk | Severity | Note / mitigation |
|---|---|---|
| Deterministic reasoner is coarse vs. an LLM reasoner | Medium | The reasoner is a **pluggable seam**; an LLM-backed `Reasoner` attaches behind the same protocol and records identically (INV-17 keeps replay deterministic). The default is auditable and self-contained (no runtime dependency), the correct foundation before the cognitive layer. |
| Goal-level estimate is coarse (no Work Packages yet at EI time) | Low | EI consumes whatever Estimation produces; `signals_from_goal` supplies factual goal-level counts, and a caller may pass richer signals. Complexity is an *influence*, absence-tolerant. Documented in `composition.py`. |
| Classification keyword signals could miss phrasing | Low | Multi-signal weighing + domain nudge + confidence; unrecognized → `generic` with a recorded assumption, never a wrong-but-confident answer. Additive vocabulary, extends without a new schema. |
| Policy queried at goal-level attributes only | Low | EI queries the *general* action-class ceiling (domain/priority) via side-effect-free `simulate`; per-action authorization remains Policy's at the action site (INV-28). EI proposes gates; it never authorizes. |
| Strategy carries a timestamp → equality needs a fixed clock | Low | The reasoning is timestamp-free and fully deterministic; only the bundle stamps recording time (INV-17, injected). Tests compare fixed-clock Strategies. |

**No constitutional conflict was discovered.** Two places pressed against the brief and were surfaced rather than silently reconciled: (a) the task lists "Context" among EI's inputs, but the authoritative input model (`engineering/02`) places Context Engineering *downstream* of Reason — EI **emits Context Objectives**, it does not consume a Context Package; "Context" is read as situational grounding (Repository Understanding + Knowledge + Preferences), which EI does consume. (b) The two guardrails that asserted "EI does not exist" / implied "no consumer touches policy" were **updated, not deleted** — their constitutional intent (estimation is a leaf feeding EI; EI queries but never evaluates policy) is now asserted in the correct P5 direction.

---

## 10. Remaining Work Before P6

EI now produces a Strategy every downstream engine can consume. Outstanding, none blocking:

1. **Planning consumption:** wire Planning to read `EngineeringStrategy` at its input boundary (the design's additive-producer property) — a Planning-side integration, not an EI change.
2. **LLM reasoner (optional):** inject an LLM-backed `Reasoner` behind the existing protocol when a runtime seam for reasoning exists; it records identically, so replay stays deterministic (shadow-adjudicable via P3 as a probabilistic class).
3. **Repository Understanding grounding:** richer approach/risk inference once Repository Intelligence (task-P4/program-P4) supplies real repository facts through `ReasoningInputs.repository_understanding`.
4. **Freeze `engineering_strategy` contract:** when a second consumer needs the shape (INV-07 discipline / program P0.4) — deferred, not precluded; the Strategy is a clean value object the freeze can adopt.

**Verdict:** P5 is functionally complete. `nexus_engineering` is the single owner of engineering reasoning; it consumes Policy, Estimation, Knowledge, and grounding without duplicating them; it produces one immutable, explainable, replayable `EngineeringStrategy`; Planning is untouched (consumption is the next step); every recommendation is explainable and reconstructs from the durable log without re-inference; and no engine, protocol, contract, or invariant was changed. **No commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_engineering` unit + durable integration | **52 passed** |
| Updated guardrails (estimation direction + policy consumer) | green in context |
| Full v2 `nexus_*` unit + integration sweep | **2533 passed**, 1 skipped |
| Lint (`ruff`) on new package + tests | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent here) — a pre-existing environment condition; the v1-app tests (`scheduling`, `config`, `health`, `state_machines`, `intelligence/briefing`, …) need the v1 `db_session`/settings fixtures and are outside the v2 sweep, exactly as in the P1–P4 reports.
