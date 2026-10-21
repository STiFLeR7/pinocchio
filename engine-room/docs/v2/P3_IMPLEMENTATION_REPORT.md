# P3 Implementation Report — Constitutional Integration Substrate

- **Date:** 2026-07-14
- **Program:** P3 (Strangler / Integration Substrate) of the Constitutional Engineering Program
- **Governing decision:** ADR-008 (Shadow Decision Migration), on ADR-007 (durable log) + ADR-001 + ADR-004
- **Rule observed:** implementation only — no redesign, no protocol/contract/invariant/ADR edits, no engine redesign, no application-logic migration, no commit.

---

## 1. Executive Summary

`nexus_integration` is the reusable **decision-migration substrate** that lets v1 and v2 coexist safely while constitutional owners replace legacy owners one at a time. It implements **Recorded Shadow Adjudication** (ADR-008 §3.2) exactly as ratified: per decision, a **legacy decision**, its **side-effect-free constitutional shadow**, and their **determinism-class-classified diff** are recorded as durable, correlated, append-only `migration.*` events (ADR-007 / INV-13 / INV-39); authority is routed by a **per-owner feature flag** (`disabled → shadow → canary → enabled`) and rolled back per owner with one atomic flag write.

The substrate is **pure coordination — no business logic**. It never plans, evaluates policy, executes, classifies intent, estimates, orchestrates, validates, or recovers. It invokes injected `legacy` / `shadow` decision callables (pure decision evaluations) and records facts; the caller performs any authoritative side effect afterward. It depends only on `nexus_core` and `nexus_infra` — **never on an engine** (guardrail-proven). Durability is transparent through P1: over `build_durable_infrastructure` every migration fact and flag transition is durable and replayable with **zero substrate-specific durable code**.

**No engine, protocol, contract, or invariant was changed.** Integration is additive DI (`build_integration`). The ADR-008 §9 entry gate is met: exact-match comparison proven on a deterministic owner (the real `nexus_policy` engine shadowing a v1-style verdict), an equivalence band proven on a probabilistic owner (intent) with no false-mismatch, side-effect isolation demonstrated, and per-owner rollback demonstrated.

**New package — `nexus_integration/`** (11 modules): `model` (flag/determinism/verdict enums + decision identity, diff, adjudication result), `flags` (durable event-sourced `FlagStore` single seam + deterministic `CanaryCohort`), `comparator` (determinism-class comparators + extensible registry + diff engine), `recorder` (the three `migration.*` facts), `coordinator` (`ShadowDecisionCoordinator` + `RollbackCoordinator`), `gateway` (transport-only `CorrelationGateway`), `events`, `ids`, `observability`, `composition` (`build_integration`), `__init__`.

**Changed — `pyproject.toml`**: added `nexus_integration` to the package list (packaging only).

**Tests** — `tests/unit/nexus_integration/` (9 files + fixtures) + `tests/integration/{test_integration_durable,test_policy_shadow}.py`.

> **Placement note.** The engineering program *suggested* WP-P3.1's flag module in `nexus_infra` and WP-P3.3 as a separate `nexus_gateway` package. The P3 task deliverable is `nexus_integration/`, so all migration primitives — including the correlation gateway — are consolidated there. This is a placement decision, not an architecture change; the gateway remains transport-only and forward-compatible with an out-of-process transport.

---

## 2. ADR Compliance (ADR-008)

| ADR-008 clause | Status | How |
|---|---|---|
| §3.2 five-stage Recorded Shadow Adjudication | ✅ | `adjudicate`: record legacy → (unless disabled) shadow → compare → record diff → route by flag; the flag states are the stages. |
| §3.2 three records are durable correlated events | ✅ | `migration.decision_recorded` / `migration.shadow_decision` / `migration.decision_diff`, one correlation stream (INV-39), append-only. |
| §3.3 comparison by determinism class | ✅ | `DeterministicComparator` (exact), `ProbabilisticComparator` (semantic hook only; never exact-match), `ExternalStateComparator` (evidence-aware); extensible registry. |
| §3.5 shadow is side-effect-free | ✅ | The substrate emits only `migration.*`; the shadow callable is a pure decision; guardrail asserts zero non-migration events under a shadow correlation. |
| §3.6 rollback is per-owner | ✅ | `RollbackCoordinator.rollback(owner)` = one atomic flag write to `DISABLED`; owner-scoped, never global; history preserved (INV-13). |
| §3.6 runtime-mutable, default-safe flags | ✅ | `FlagStore` default-off; a flip changes routing with no redeploy; v1 authoritative until a flag enables v2. |
| §9 entry gate (one deterministic + one probabilistic owner) | ✅ | `test_policy_shadow.py`: policy exact-match; intent equivalence band with no false-mismatch. |
| Determinism-class routing honors ADR-004 boundaries | ✅ | Cognition (LLM) never exact-matched; coordination/governance decisions do. |

The substrate builds only the ADR-008 machinery (§6: "P3 builds the feature-flag host, the three event types and comparator, and the correlation gateway"). It performs **no** per-owner migration itself — that is P2/P4–P10 consuming this substrate.

---

## 3. Constitution Compliance

- **INV-02 (one owner per decision):** the substrate coordinates *migration of authority* between exactly two named parties (legacy, constitutional) per `DecisionIdentity.owner`; it never fuses owners. The correlation gateway is transport-only (no god-object).
- **INV-07 (one schema):** no new domain object or alternative representation; migration facts are `Event`s (the one envelope). The dual-representation window ADR-008 permits is time-boxed per owner, not introduced here.
- **INV-13 / INV-17 (event authority, replay):** flags and decisions are events; `FlagStore.rebuild` and the durable log make migration state a projection — same events → same state/verdict.
- **INV-29 (decides/authorizes, never executes):** the substrate performs no side effect beyond recording its own facts; shadow computation is side-effect-free.
- **INV-39 (correlated interaction):** the three facts of a decision share its correlation; flag transitions share a per-owner lifecycle stream.
- **Dependency direction (INV-01):** `nexus_integration → {nexus_core, nexus_infra}` only; a guardrail asserts no engine import.

No constitutional conflict was discovered.

---

## 4. Migration Architecture

```
                        per-owner FeatureFlag (durable, versioned)
                        disabled → shadow → canary → enabled
                                     │
DecisionIdentity(owner, decision_id, correlation, cohort_key)
        │
        ▼
 ShadowDecisionCoordinator.adjudicate(legacy(), shadow(), determinism_class)
        │
        ├─ record legacy   → migration.decision_recorded ─┐
        ├─ (active) shadow → migration.shadow_decision    ├─ one correlation stream (INV-39)
        ├─ compare(class)  → migration.decision_diff  ────┘   durable, append-only (ADR-007)
        └─ route authority by flag → AdjudicationResult(authoritative_value, authority, diff)
                                     │
                        caller performs the authoritative side effect
```

- **Reusability:** `legacy`/`shadow` are zero-arg decision callables; `determinism_class` selects the comparator; `comparator`/`cohort` are overridable per call. The same coordinator serves every owner (Policy first, then Intent, EI, Orchestration, Recovery, …).
- **Single flag seam:** `FlagStore.state(owner)` is the only flag read (guardrail: no scattered reads) — a flip re-routes everywhere at once.
- **Correlation gateway:** the transport seam the recorder emits through; in-process today, out-of-process later without changing the recording contract.

---

## 5. Replay Validation (`test_integration_durable.py`)

- **Decision recording durable:** the three facts survive reopening the SQLite file.
- **Replay reconstructs migration history:** the `migration.decision_diff` stream replays as the exact ordered `(decision_id, verdict)` history.
- **Deterministic replay:** two independent `FlagStore.rebuild` passes over the same log yield identical snapshots.
- **Feature-flag replay & rollback replay:** flag transitions (including a rollback to `disabled`) reconstruct exactly from the log after restart.
- **Restart preserves migration state:** flags + version reconstruct from the durable log.
- **Correlation preserved end-to-end:** the three facts of a decision all carry its correlation id after restart (INV-39).

---

## 6. Shadow Validation

- **Shadow produces no side effects** (`test_coordinator.py::test_shadow_run_emits_only_migration_events`, `test_guardrails.py::test_shadow_never_mutates_production`, `test_policy_shadow.py::test_policy_shadow_is_side_effect_free`): the only events under a shadow correlation are `migration.*`; the `nexus_policy` engine used as the shadow runs with no emitter.
- **Diff generation deterministic** (`test_comparator.py::test_diff_generation_is_deterministic`).
- **Injected divergence caught** (`test_policy_shadow.py::test_intent_owner_real_divergence_is_flagged`).
- **No false-mismatch on LLM decisions** (`test_policy_shadow.py::test_intent_owner_probabilistic_no_false_mismatch`): token-different-but-equivalent → `EQUIVALENT`, not `MISMATCH`; without a hook → `UNDETERMINED`, never exact-match.
- **Exact-match works on the deterministic owner** (`test_policy_owner_deterministic_shadow_matches_v1`): the v2 policy engine reproduces v1's verdict across the matrix.

---

## 7. Rollback Validation (`test_rollback.py`, `test_guardrails.py`)

- **Restores legacy authority** immediately (`enabled` → rollback → next adjudication is `LEGACY`).
- **Per-owner, never global:** rolling back `policy_engine` leaves `intent_resolution` untouched.
- **Deterministic & observable:** a single flag write to `DISABLED`, telemetry incremented.
- **Durable & replayable:** the rollback is a `migration.flag_set` event; it replays after restart.
- **History preserved:** rollback only appends; the full decision/diff history remains (INV-13).

---

## 8. Operational Impact

- **First live seam.** Any owner can now run in shadow against v1, producing a durable, replayable diff stream — the input to the shadow-diff dashboard (migration telemetry counters: `migration.decision_recorded`, `migration.diff.<verdict>`, `migration.authoritative.<side>`, `migration.flag.<state>`, `migration.rollback`).
- **Default-safe:** every owner is `DISABLED` (legacy authoritative) until a flag is flipped; no behavior changes on adoption.
- **Storage:** rides the infrastructure context — in-memory by default, durable SQLite when durable; no new stores.
- **Cutover gating:** the diff stream lets a human/automation block cutover until the equivalence score meets ADR-008's threshold; the substrate provides the evidence, not the gate policy (which is per-owner, later).

---

## 9. Risks

| Risk | Severity | Note / mitigation |
|---|---|---|
| Caller passes an impure `shadow` that mutates production | Medium | Contract: `legacy`/`shadow` are pure decision evaluations; the guardrail proves the *substrate* emits only `migration.*`, but a caller-supplied effectful shadow is the caller's defect. Per-owner shadow adoption should wrap a side-effect-free engine (as the policy fixture does). |
| Reused `decision_id` under one correlation | Low | Ids are content-addressed by identity; a duplicate id with different content would raise on the durable append. `decision_id` uniqueness is the caller's responsibility (documented on `DecisionIdentity`). |
| Probabilistic equivalence band mis-tuned → false equivalence | Medium | Bands are injected per owner and versionable (ADR-008 §10); `UNDETERMINED` (human) is the safe default when no band is supplied. |
| Canary cohort instability | Low | Membership is a deterministic hash of a stable `cohort_key` (ADR-008 R4); proven pinned. |
| Gateway grows logic (god-object) | Low | Transport-only; guardrail keeps flag reads at the `FlagStore` seam and asserts no engine import. |

---

## 10. Remaining Work Before P4

P4 (Repository Intelligence) is off the critical path and does not depend on P3. The substrate is, however, the prerequisite for every *cutover*. Outstanding, none blocking P4:

1. **Per-owner Stage-1 adoption (P2 Policy first, then P7/P8/…):** wire each owner's real legacy site to `adjudicate` with its determinism class and (for probabilistic owners) an equivalence band. This is per-owner migration work, not substrate work.
2. **Decomposition map artifact** (ADR-008 §3.1) for conflated owners (`planner.py` → Intent/EI/Policy) before their Stage 1.
3. **Shadow-diff dashboard:** the P3 DoD's operational gate — a view over the `migration.*` telemetry/event stream (the data exists; the view is an ops surface).
4. **Equivalence-score threshold policy** per owner (ADR-008 §9): the substrate records verdicts; the cutover threshold is a per-owner decision recorded when that owner migrates.

**Verdict:** P3 is functionally complete against ADR-008. Recorded Shadow Adjudication is fully implemented; feature flags are deterministic, durable, versioned, and default-off; legacy and constitutional decisions execute side-by-side with no side effects; decision history is durable, replayable, and observable; rollback is deterministic and per-owner; and no engine, protocol, contract, or invariant was changed. **No commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_integration` unit + integration | **52 passed** |
| P1 + P2 suites (unchanged) | **320 passed** |
| Full v2 unit + integration sweep | **2447 passed**, 1 skipped, 1 pre-existing `--noconftest` fixture error (`test_state_machines.py` needs the v1 `db_session` conftest fixture — unrelated to P3) |
| Lint (`ruff`) on new package + tests | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent here) — a pre-existing environment condition; the v2 suites are plain pytest functions.
