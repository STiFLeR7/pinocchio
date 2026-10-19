# P14 — Constitutional Learning Loop & Human Interaction Surface Report

Status: Complete (implementation; not committed — awaiting explicit release instruction)
Scope: two additive threads over the P13 unified pipeline — (A) a governed, deterministic learning loop,
(B) the first constitutional Human Interaction façade. **No constitutional owner, contract, ADR, or
invariant changed.** Tracked-file edits are all additive: a governance *default* in `nexus_policy`
(`knowledge_grounding_baseline`, data only), the new-package addition to the CI mypy target, and the
pre-existing P13 durable seam on `PipelineBuilder`.

---

## Executive Summary

P13 unified the platform into one deterministic Goal→Knowledge pipeline but left the loop open: the
driver *wrote* Knowledge yet did not *read* it, so a second execution could not be grounded by the first.
P14 closes that loop and puts a human surface on the platform — additively, preserving every owner.

- **A — Learning loop.** Prior Knowledge is now an **optional, governed** grounding input flowing
  **Knowledge → Engineering → Context → Planning**. A deterministic `KnowledgeSelector` retrieves prior
  Knowledge (the Knowledge engine's read-only `serve`), governs its admission through the Policy engine
  (a `knowledge_grounding` governed action, permitted by an overridable allow-baseline), and supplies it
  to Engineering (its existing `knowledge=` input) and to the **P9 grounded-Context** path
  (`GroundingInputs.knowledge` — INV-06, read-only). Planning still never queries Knowledge (INV-26); it
  is grounded indirectly through the now-Knowledge-aware Strategy and Context Package. Selection is a pure
  function of the Knowledge store + Goal + Policy — deterministic, replayable, provenance-recorded
  (references only), no LLM ranking, no Knowledge mutation.

- **B — Human Interaction surface.** `nexus_human_interaction` is the first **constitutional operator
  façade**: submit a Goal, inspect pipeline status / execution history / execution graph / Knowledge,
  replay and restart sessions, and have execution lineage explained — every operation invoking **only**
  the `ConstitutionalPipeline`. No engine is user-callable; the façade owns request translation, response
  formatting, session lookup, and progress reporting, and **owns no reasoning**. It records durable
  `interaction.*` facts so an operator session replays exactly and a restart resumes without replaying
  completed constitutional stages.

**Validation:** 23 new tests, all green; **full v2 sweep 2 853 passed, 1 opt-in skip, 0 regressions**
(1 pre-existing `test_state_machines` `db_session` error from the `--noconftest` strip, unrelated);
**95 architecture guardrail tests pass**; **18 event producers, each unique** (`human_interaction` is the
18th); mypy-strict + ruff clean. First execution records Knowledge; the second consumes it; deterministic
replay + restart hold end-to-end and through the operator surface.

---

## Constitutional Compliance

Audited against the 39 invariants and the decision-ownership table. **No violation introduced.**

| Concern | Evidence | Verdict |
|---|---|---|
| **INV-06** Context consumes Knowledge; never owns it | Knowledge is supplied to the **grounded Context** path (`GroundingInputs.knowledge`, read-only, by value); Context remains the sole producer of the Context Package. | ✅ Holds |
| **INV-26** Planning never depends directly on Reflection; learning reaches Planning only through persisted Knowledge | The loop is Knowledge → Engineering → Context → Planning; Planning consumes the Strategy + Context Package, never Knowledge directly (guardrail-proven — `nexus_planning` references no Knowledge query). | ✅ Holds |
| **INV-24** Knowledge is evidence-backed | The selector only *reads* Knowledge (`serve`); ingestion remains validation-gated. Nothing mutates stored Knowledge. | ✅ Holds |
| **INV-28 / 30 / 31** Policy is the sole evaluator; fail-closed; explainable | Admission is a **governed** `knowledge_grounding` decision the Policy engine evaluates; the allow-baseline lives in `nexus_policy` (the only package that constructs `PolicyDecision` — guardrail-proven); a deny policy filters grounding out; the verdict carries a reasoning trace. | ✅ Holds |
| **INV-02 / one owner per event** | Two new single-producer namespaces: `pipeline.knowledge_grounded` (`producer=pipeline`) and `interaction.*` (`producer=human_interaction`, the 18th unique producer). | ✅ One owner each |
| **INV-07** one schema per object | The learning + interaction models are `ValueObject` projections / DTOs; no new frozen domain object (guardrail-proven, no `DomainObject` base). | ✅ No competing model |
| **INV-11** Observation owned by Supervision | Learning + interaction observability are counters over the P1 sink; operator metadata is projected read-only. | ✅ Holds |
| **INV-13 / 14 / 17** log is truth; state derived; capture, don't recompute | Grounding provenance (`pipeline.knowledge_grounded`) and interaction sessions reconstruct from the log; selection re-derives deterministically from the durable Knowledge store. | ✅ Holds |
| **INV-18** resume from checkpoint, never from Goal | Operator `restart` drives the pipeline's log-seeded resume — completed constitutional stages are reconstructed, not replayed. | ✅ Holds |
| **Human Interaction owns no reasoning** | The façade imports no engine package and invokes only `ConstitutionalPipeline` (guardrail-proven); no engine became user-callable. | ✅ Holds |

**The one governance-owner touch is additive and *strengthens* compliance:** `knowledge_grounding_baseline`
is a data-only governance default added to `nexus_policy` alongside `v1_seed_policies`. Placing it in the
governance package (rather than the consumer) keeps `PolicyDecision` construction inside `nexus_policy` —
satisfying the standing guardrail that *no consumer emits a policy verdict* (INV-28).

---

## Learning Loop Architecture

One additive module — `nexus_workflows/spine/learning.py` — plus the coordinator wiring:

```
Intent → Goal
      │                         KnowledgeSelector.select(goal, subject, kind)
      ▼                           ├─ knowledge.serve(query)         # retrieve (read-only, INV-16 order)
  [grounding: select prior        └─ policy.simulate(knowledge_grounding)  # govern (INV-28; allow-baseline)
   Knowledge, once per run] ──────────► KnowledgeSelection(items, references, governed, decision, trace)
      │                                        │                    │
      ▼ knowledge=items                        ▼ references-only    ▼ items (by value, read-only)
  Engineering ── Strategy ─────────────► pipeline.knowledge_grounded    grounded Context (GroundingInputs.knowledge)
      ▼                                     (provenance fact)              ▼  (INV-06; context.grounding.selected)
  Context Package (Knowledge-grounded) ───────────────────────────────► Planning ── ExecutionPlan
```

- **`KnowledgeSelector`** — retrieve (`serve`) + govern (`simulate` a governed `knowledge_grounding`
  decision) → `KnowledgeSelection`. Deterministic (pure over Knowledge store + Goal + Policy); no LLM,
  no embeddings, no mutation.
- **Coordinator integration** — a lazy, cached `_grounding(...)` runs the selection **once** per run and
  records one `pipeline.knowledge_grounded` provenance fact; both the Engineering stage
  (`strategize_for_goal(knowledge=...)`) and the now-grounded Context stage
  (`grounded_context.assembler.assemble(GroundingInputs(..., knowledge=...))`) consume the same
  selection. A restart that resumes at Context (Engineering already reconstructed) re-derives the same
  selection deterministically.
- **Optionality + governance** — `build_constitutional_pipeline(..., learning=True)` registers the
  overridable allow-baseline and wires the selector; `learning=False` is the P13 driver unchanged. A
  higher-specificity deny policy filters grounding out at runtime (proven: `governed=False`, 0 admitted).

Demonstrated (`test_learning_loop.py`, `test_human_interaction.py`): run one grounds 0 and records
Knowledge; run two (sharing only the Knowledge store) grounds ≥ 1 and still reaches evidence-backed
Knowledge; grounding is deterministic; a deny policy zeroes it; `learning=False` reproduces P13.

---

## Human Interaction Architecture

One additive package — `nexus_human_interaction` — a façade over the pipeline (8 modules):

| Module | Responsibility |
|---|---|
| `facade.py` | `HumanInteraction` — submit / restart (drive the pipeline) + status / history / execution_graph / knowledge / replay / explain_lineage (project it). Invokes **only** `ConstitutionalPipeline`. |
| `model.py` | `OperatorRequest` (operator DTO → `SpineRequest`), `InteractionSession` (ValueObject projection), and read-only formatted views (`InteractionResponse` / `InteractionStatus` / `ExecutionGraphView` / `KnowledgeView` / `LineageView`). |
| `events.py` | The additive `interaction.*` facts + `build_event` (`producer=human_interaction`). |
| `session.py` | `reconstruct_interaction_session` — rebuild the operator session from the log. |
| `composition.py` | `build_human_interaction(infra, …)` — wires the façade over the pipeline (learning-on). |
| `reference.py` | The canonical `reference_operator_request`. |
| `observability.py` | Operator-session counters (instrumentation only). |
| `__init__.py` | Public exports. |

The pipeline gained a small **read-only inspection surface** (`ConstitutionalPipeline.history / session /
lineage / execution_graph / execution_state / inspect_knowledge`) — thin log projections and the one
Knowledge read delegated to its sole owner — so the façade never touches an engine. Dependency direction
is one-way (`nexus_human_interaction → {nexus_workflows.spine, nexus_core, nexus_infra}`); the façade
imports no engine package (guardrail-proven). `nexus_operator` (the pre-P13 productization experience over
the incumbent `WorkflowCoordinator`) is untouched — the constitutional surface is new and drives the P13
pipeline.

---

## Knowledge Provenance

Every grounded run records exactly what grounded it, **references only**:

- **`pipeline.knowledge_grounded`** (one per run) embeds the query subject/kind, the governance verdict
  (`governed`, `decision`, reasoning trace), the selected Knowledge **references + ids**, and the count —
  never the Knowledge objects (proven: `"items" not in payload`).
- **`context.grounding.selected`** (the P9 grounding fact) records the deterministic relevance selection —
  which grounding artifacts (including `source="knowledge"`) were included/omitted and *why*.
- The operator inspects provenance via `explain_lineage(...)`, which surfaces the grounding record and the
  execution lineage; `SpineRun.knowledge_grounding` carries the same selection to the façade.

Provenance is durable and replayable: a reopened log reconstructs the `pipeline.knowledge_grounded` fact
exactly, and re-serving from the durable Knowledge store re-derives the identical selection.

---

## Replay Validation

- **Learning:** grounding replays from the durable log — the provenance fact reconstructs exactly, and the
  selection re-derives deterministically (pure over the shared Knowledge store). Two independent grounded
  runs yield identical plan / ExecutionState / selected-ids.
- **Interaction:** a fresh façade over a reopened durable file reconstructs the operator session
  (`replay(...)` → submitted, responded, completed, correct pipeline-session reference) with no
  re-execution. The operator + pipeline event stream is byte-identical across independent runs
  (`test_operator_flow_is_deterministic`).

---

## Restart Validation

- **Interaction restart (durable, proven):** an operator `submit(..., control=stop_after ACTUATION)`
  pauses; a fresh façade over the reopened file `restart(...)` resumes to completion with the front +
  actuation stages **reconstructed** (`reconstructed_stages = intent … actuation`) and only the
  Validate→Learn tail **executed** — completed constitutional owners are not re-invoked (INV-18). This is
  the P13 durable restart surfaced through the operator façade, plus an `interaction.resumed` fact.

---

## Remaining Architectural Gaps

Documented honestly (none is a violation):

1. **Approval surface is enforced but not yet interactive.** Execution Actuation *pauses* at an ungranted
   approval gate, and the façade can *restart* a paused session — but there is no interactive
   grant/deny channel that collects an operator decision and re-drives with `granted_gates`. The seam
   exists (the pause + `interaction.resumed`); wiring an approval request/response exchange is the natural
   next Human-Interaction increment. **Recommended for P15.**
2. **Grounding relevance is subject/kind-scoped.** The selector serves by `(subject, kind)` and admits the
   governed set; finer relevance (per-goal keyword selection) is delegated to the P9 grounding selector
   downstream. Deterministic and sufficient, but a richer query (confidence floor, limit, goal-scoped
   subjects) would sharpen what grounds a run.
3. **Cross-run learning requires a shared Knowledge store.** As designed (INV-26 — learning flows via the
   record), run two consumes run one only when they share Knowledge repositories; a production deployment
   must persist Knowledge durably across runs (the durable seam supports it; wiring a shared durable
   Knowledge store is an operations concern).
4. **P12 cosmetic findings persist, not worsened** (F-5 two `PolicyContext` classes; F-6 `execution.*`
   producer). Unchanged; nothing added depends on them.

---

## Production Readiness Assessment

**READY** — as a *governed, learning, operable constitutional platform*: one deterministic Goal→Knowledge
pipeline that now (a) grounds future executions in prior Knowledge under governance, deterministically and
replayably, and (b) exposes submit / inspect / replay / restart / explain through a single constitutional
operator façade that never bypasses the platform. 2 853 green tests, 0 regressions, 0 invariant
violations, 18 single-owner producers.

**NOT YET** — *fully autonomous*: the interactive approval exchange (grant/deny surface) is the remaining
Human-Interaction increment before approval-gated unsupervised operation, and the Scheduler / Operations
planes remain unbuilt (on the roadmap, deliberately after a coherent pipeline + human surface).

---

## Recommendation for P15

**P15 — Constitutional Approval Exchange & Operations Plane.** Two threads, in order:

1. **Interactive approval (close Gap 1):** an additive Human-Interaction request/response exchange over the
   existing Actuation approval pause — surface a governed approval request, collect the operator decision,
   and re-drive the paused pipeline with `granted_gates`, all recorded as `interaction.*` facts. This is
   the last seam before approval-gated autonomy.
2. **Operations plane:** derive platform health, cost, and lineage metrics from the one shared log
   (read-only projections, no new ownership), giving operators a durable operational view of the pipeline
   they now drive.

---

## Success Criteria

| Criterion | Result |
|---|---|
| Knowledge becomes a governed input to future executions without violating ownership | ✅ Knowledge → Engineering → Context → Planning; governed (allow-baseline, deny filters); Knowledge engine sole owner; Planning never queries it (INV-26). |
| Human Interaction exposes the platform without bypassing it | ✅ The façade invokes only `ConstitutionalPipeline`; no engine is user-callable (guardrail-proven). |
| Replay and restart remain deterministic | ✅ Grounding + interaction replay; durable interaction restart reconstructs completed stages. |
| No constitutional contracts, ADRs, or invariants change | ✅ None touched; the one governance-owner edit is a data-only default that *strengthens* the INV-28 guardrail. |
| All tests pass with zero regressions | ✅ 2 853 passed, 1 opt-in skip, 0 regressions; 95 guardrails green; mypy/ruff clean. |

---

## Validation Summary

- **23 new tests:** learning — `test_learning.py` (4: governed-on, deny-filters, deterministic,
  references-only provenance), `test_learning_loop.py` (6: records→consumes, deterministic grounding,
  governance filters, durable references-only provenance, learning-disabled = P13); interaction —
  `nexus_human_interaction/test_facade.py` (4) + `test_guardrails.py` (4: no-engine façade, no domain
  object, ValueObject session, single producer), `test_human_interaction.py` (5: submit→Knowledge,
  determinism, durable replay, durable restart, learning-loop-through-the-surface).
- **Full v2 sweep: 2 853 passed, 1 skipped (opt-in), 0 regressions** (1 pre-existing `test_state_machines`
  `db_session` error from `--noconftest`).
- **95 architecture guardrail tests pass** (P13's 91 + 4 new). **18 event producers, each unique.**
  **mypy-strict + ruff** clean; the new `nexus_human_interaction` package added to the CI mypy target.
- **Incumbent surface:** `git status` shows four additive tracked-file edits — the CI mypy target, the
  `nexus_policy` governance default (data only), the `nexus_policy` export, and the pre-existing P13
  `PipelineBuilder` durable seam — plus the new `nexus_human_interaction/` package, the learning module in
  `nexus_workflows/spine/`, and the new tests. No owner behavior, contract, ADR, or invariant changed.

Per the rules, **no commit was made**.
