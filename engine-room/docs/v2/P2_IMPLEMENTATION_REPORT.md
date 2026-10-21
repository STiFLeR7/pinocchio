# P2 Implementation Report — Policy Engine

- **Date:** 2026-07-14
- **Program:** P2 (Policy Engine) of the Constitutional Engineering Program
- **Governing decisions:** ADR-004 (Policy Engine & Governance), ADR-001 (event-sourced state), ADR-007 (durable persistence)
- **Rule observed:** implementation only — no redesign, no protocol/contract/invariant/ADR edits, no engine redesign, no commit.

---

## 1. Executive Summary

`nexus_policy` is now the **single constitutional owner of governance decisions** (INV-28). It gives v2 the executable policy evaluator it provably lacked: v2's `PolicyResolver` (in `nexus_harness`) explicitly never evaluates governance, and only v1's async `policy_service` did — and v1's is a config-registry, not a condition-tree evaluator.

The engine consumes the **frozen** `policy` contract and `nexus_core.domain.Policy` unchanged (INV-07 — no new schema), evaluates a `DecisionRequest` against the enabled policy set through a data-driven condition tree (ADR-004 §3.1, no DSL), resolves conflicts by the fixed order **Specificity → Priority → Version → Default Policy**, and returns an immutable, explainable `PolicyEvaluation` drawn from the closed `PolicyDecision` set. It is **fail-closed** (INV-30), **deterministic and replayable** (ADR-004 §8, INV-17), **explainable** (INV-31), and every decision is a **correlated durable event** (INV-39, WP-P2.2).

Durable persistence is **transparent through P1**: the engine emits via the `InfrastructureContext` and persists policies through its `PolicyRepository`, so a context from `build_durable_infrastructure` (ADR-007) makes registrations and decisions durable with **zero policy-specific durable code**.

**No engine was modified.** No `PolicyEngine` consumer was wired (that is P5+); P2 delivers the evaluator and proves, by static guardrail, that no other package evaluates policy.

**New package — `nexus_policy/`** (11 modules): `model` (DecisionRequest / PolicyEvaluation / PolicyRef — the deterministic decision model), `conditions` (the data-driven matcher + specificity), `precedence` (conflict resolution), `defaults` (Default Policy + v1 seed loader), `registry` (version-addressable, event-sourced projection), `engine` (the evaluator), `events`, `ids`, `observability`, `composition` (`build_policy`), `__init__`.

**Changed — `pyproject.toml`**: added `nexus_policy` to the package list (packaging only).

**Tests** — `tests/unit/nexus_policy/` (7 files) + `tests/integration/test_policy_durable.py`.

---

## 2. Architecture Compliance

| Requirement | Status | How |
|---|---|---|
| Policy Engine is the **sole** evaluator (INV-28) | ✅ | Only `nexus_policy` returns a `PolicyDecision`; static guardrail greps every consumer package and asserts none references it. |
| Engine **decides, performs no action** (INV-29) | ✅ | `evaluate` returns a value and emits one *fact*; runs no approval workflow, mutates no plan/goal. With no emitter its only output is the returned object. |
| **Fail-closed** default (INV-30) | ✅ | Governed request, no match → Default Policy denies; malformed/erroring evaluation → deny; only explicitly ungoverned classes are allow-by-default. |
| **No embedded DSL** (ADR-004 §3.1) | ✅ | `conditions` is a structured mapping tree of typed predicates; `conditions.py` is its only interpreter. |
| Deterministic conflict resolution | ✅ | Fixed order Specificity → Priority → Version, with identity as a total final tiebreak (`precedence.resolve`). |
| Closed decision set | ✅ | Decisions come only from `PolicyDecision`; recovery strategies (Retry/Rollback/Abort) are structurally impossible. |
| Single approval taxonomy (ADR-004 §3.3) | ✅ | `RequireApproval` carries an `ApprovalTaxonomy` level; unspecified maps to `HumanReview`. |
| Reuses existing infra; no duplication | ✅ | Reuses `InfrastructureContext`, `PolicyRepository`, `Observability`, the event store/bus. No new persistence layer; no new registry protocol. |
| No engine behaviour changed | ✅ | Planning/Runtime/Validation/Recovery/Reflection/Knowledge/Workflow untouched; only DI point is the new `build_policy` composition. |

---

## 3. ADR Compliance

- **ADR-004 (Policy Engine & Governance).** Data-driven condition tree (§3.1); specificity defined as bound-predicate count; conflict order and Default Policy as specified; Policy-Engine-decides / Governance-authorizes boundary held (§3.2 — engine performs no action); one approval taxonomy (§3.3); determinism guaranteed for evaluation, not cognition (§3.5 — the engine is a pure function of request + policy set); v1 `_ACTION_POLICY`/defaults migrated as the seed set (§9).
- **ADR-001 (event-sourced).** The registry is a *projection*: `policy.registered` is authority, the in-memory index and `PolicyRepository` are derived; `rebuild(events)` reconstructs the registry from the log. Decisions are events; state is derived.
- **ADR-007 (durable persistence).** No policy-specific durable code — the engine rides the P1 substrate. Over `build_durable_infrastructure` the decision log and policy read-model are durable; the registry rebuilds from the durable log after restart.
- **ADR-008 (shadow migration).** Untouched. The engine is decision-side-effect-free and `simulate()` is fully side-effect-free, which is exactly the property ADR-008 shadow adjudication requires; no flag/shadow wiring was added (that is P3).

---

## 4. Contract Compliance (`contracts/policy.md`)

| Contract clause | Status |
|---|---|
| §1 one job: expresses *conditions → decision (+ constraints)* as data | ✅ evaluated by the engine, never self-executing |
| §4 required fields consumed as frozen | ✅ identity, version, purpose, conditions, decision, priority, owner |
| §5 optional fields honored | ✅ constraints surfaced on the result; `approval_requirement`, `category`, `governed_action_class` used |
| §6 INV-28/29/30, closed decision set, deterministic resolution, no DSL, INV-17 replay, INV-31 explainable, side-effect-free simulation | ✅ all exercised by tests |
| §8 versioning is the unit of change; Default Policy permanent; determinism preserved | ✅ registry is version-addressable; Default Policy is deny-only; evaluation captured as event data |

The condition-tree *internal shape* (left "intentionally unspecified at Phase 1" by the contract, `Struct`) is defined by this implementation — `{all|any|not|{attr,op,value}}` — as an **additive** predicate vocabulary (ADR-004 §5, §8): new ops/attributes extend it without a DSL and without breaking existing trees.

---

## 5. Invariant Validation

| Invariant | Test |
|---|---|
| INV-28 sole evaluator | `test_guardrails.py::test_no_consumer_emits_a_policy_verdict` (parametrized over all 18 consumer packages) |
| INV-29 decides, no action | `test_guardrails.py::test_engine_performs_no_action_only_returns_a_value`; `test_engine.py::test_require_approval_reports_level_but_performs_no_action` |
| INV-30 fail-closed | `test_engine.py::{test_fail_closed_no_matching_policy_denies, test_fail_closed_malformed_policy_denies}`; `test_composition.py::test_build_policy_without_seed_is_empty` |
| INV-31 explainable | `test_engine.py::test_explainability_trace_and_refs` |
| INV-17 replay w/o reinference | `test_provenance.py::test_replay_reconstructs_authorization_history`; `test_policy_durable.py::test_full_authorization_history_replays_after_restart` |
| INV-16 idempotent | `test_provenance.py::test_identical_evaluation_is_idempotent_in_the_log` |
| INV-39 correlated | `test_provenance.py::test_decision_event_is_correlated_and_carries_the_verdict` |
| INV-15 lifecycle event | `test_registry.py::test_register_emits_one_registered_event` |
| INV-07 one schema | Reuses `nexus_core.domain.Policy`; no alternative representation introduced |

---

## 6. Determinism Validation

Evaluation is a pure function of (request, enabled policy set). Proven:
- **Identical input → identical output:** `test_engine.py::test_determinism_identical_input_identical_output`.
- **Conflict-resolution truth table:** `test_precedence.py` (specificity dominates; priority breaks specificity ties; version breaks priority ties; identity is the total final tiebreak; numeric version ordering).
- **Replay-after-restart:** `test_policy_durable.py::test_same_verdict_across_restart` — rebuild the registry from the durable log and re-evaluate → identical decision and matched policy.

The one captured-as-data value (INV-17) is the event timestamp, injected via a `now` callable so decisions and the value objects stay timestamp-free; the decision event id is a **content hash of the payload**, so an identical decision is idempotent in the log and a changed outcome is a new fact.

---

## 7. Durable Persistence Validation (`test_policy_durable.py`)

- **Decision events durable & correlated:** written through `build_durable_infrastructure`, visible after reopening the file, carrying the correct correlation id and verdict.
- **Registry rebuilds from durable log:** the four seed policies reconstruct from `policy.registered` facts after restart.
- **Same verdict across restart** and **full authorization history replays after restart**.

All of this rides P1 unchanged — there is no `Durable*` policy class; the durability is a property of the injected `InfrastructureContext`.

---

## 8. Integration Points

- **Consumes:** `nexus_core.domain.Policy`, the `PolicyDecision`/`ApprovalTaxonomy`/`PolicyCategory`/`PolicyStatus` enums, and the `EventEmitter`/`Repository` protocols — all frozen/foundational.
- **Reuses:** `InfrastructureContext` (emitter + `policies` repository + observability). `build_policy(infrastructure)` is the single new DI seam.
- **Does not yet wire any consumer.** Planning/Orchestration/Execution/Operator will *query* the engine with a `DecisionRequest` in later programs (P5–P8, P10). Until then the guardrail proves none of them evaluate policy. The `PolicyRegistry` protocol in `nexus_core.registries` is satisfied by `InMemoryPolicyRegistry`.
- **Dependency direction:** `nexus_policy → {nexus_core, nexus_infra}` only. It deliberately does **not** depend on `nexus_runtime` (it re-declares no timestamp primitive; it injects a `now` callable) so the foundational Policy Engine stays below the engines that consume it (INV-01).

---

## 9. Operational Impact

- **Verdict parity with v1 out of the box:** `build_policy(..., seed=True)` loads the v1-migrated governance defaults (allowed runtimes, command blacklist, required runtime policy) so the engine reproduces v1's allow/deny for the governed `execution` action class (regression-tested, `test_regression_v1.py`).
- **Storage:** rides the infrastructure context — in-memory by default, one SQLite file when durable. No new stores.
- **Observability:** derived counters (`policy.evaluated`, `policy.decision.*`, `policy.default_applied`, `policy.registered`) over the existing sink; never authoritative.
- **Default posture:** governed-by-default and deny-by-default (INV-30); an action is allow-by-default only when the request explicitly marks its class ungoverned.

---

## 10. Performance

Evaluation is O(n) over the enabled set (n = 4 seed policies today): one condition-tree walk per policy, one linear precedence pass, one content-hash for the event id. No I/O in the decision path itself; persistence cost is the P1 append. The full 87-test policy suite (in-memory + durable) runs in ~0.4 s. No benchmark harness was built (out of P2 scope); a decision-latency budget attaches at the P3 flagged rollout.

---

## 11. Risks

| Risk | Severity | Note / mitigation |
|---|---|---|
| v2 verdicts diverge from v1 during convergence | Medium | Seed set is regression-tested against a transcription of v1's checks; **shadow-equivalence before cutover is P3** (ADR-008), not P2. |
| Seed set covers governance verdicts only, not v1's stateful operational gates (semaphores, branch/git, repo registry) | Low (by design) | Those are operational I/O, not policy *decisions* a condition tree expresses; they remain in their owners. Documented in `defaults.py`. |
| Missing request attribute → predicate is non-match (not deny) | Low | Deterministic and fail-safe (no allow can fire spuriously); the regression matrix supplies complete attribute sets, as v1 does. Documented in `conditions.py`. |
| Registry `enabled()` returns latest-per-identity; multiple enabled versions of one identity are not co-evaluated | Low | Matches the lifecycle model (a new version disables the prior); the Version tiebreak in precedence remains as defense. |
| Condition-tree shape is engine-defined (contract left it open) | Low | Additive predicate vocabulary (ADR-004 §5/§8); extends without a DSL or an ADR. |

**No constitutional conflict was discovered.** Where the task pressed against the letter — "regression vs. v1 policy defaults" — v1's evaluator turned out to be a config registry, and its actual *verdicts* live in `governance.py`; those data-driven verdicts are the seed set (ADR-004 §9 explicitly names them so). This is surfaced here rather than silently reinterpreted.

---

## 12. Remaining Work Before P3

P3 (Strangler Integration Substrate) depends on the evaluator **existing**, which it now does. Outstanding, none blocking P3:

1. **Flag/shadow rollout (P3, ADR-008):** gate v2 evaluation behind a flag and run it in shadow against v1 verdicts before cutover. The engine is already shadow-ready — `simulate()` is fully side-effect-free.
2. **Consumer wiring (P5–P8, P10):** Planning/Orchestration/Execution/Operator query the engine with a `DecisionRequest` at their governance gates; the INV-28 guardrail will extend to assert they *query* but never *evaluate*.
3. **ADR-009 (Policy Convergence):** formalize the v1→`nexus_policy` migration inventory beyond the seed set (the engineering program lists it as required before P2 cutover; the seed set + regression parity is the evidence base).
4. **Decision-latency budget:** measured at the flagged rollout (P3).

**Verdict:** P2 is functionally complete against ADR-004 and the frozen `policy` contract. `nexus_policy` is the sole, fail-closed, deterministic, event-sourced evaluator; verdict parity with v1 defaults is proven; every decision is a correlated durable event; durability is transparent through P1; and no engine, protocol, invariant, or ADR was changed. **No commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_policy` unit + durable integration | **87 passed** |
| INV-28/29 guardrails | **21 passed** |
| Existing infra + durable (P1, unchanged) | **233 passed** |
| Full v2 unit + integration sweep | **2395 passed**, 1 skipped, 1 pre-existing `--noconftest` fixture error (`test_state_machines.py` needs the v1 `db_session` conftest fixture — unrelated to P2) |
| Lint (`ruff`) on new package + tests | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent here) — a pre-existing environment condition; the v2 suites are plain pytest functions.
