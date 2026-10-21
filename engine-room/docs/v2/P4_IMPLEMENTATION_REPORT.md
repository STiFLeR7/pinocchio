# P4 Implementation Report — Estimation Foundation

- **Date:** 2026-07-14
- **Program:** P4 (Estimation Foundation) as briefed
- **Governing decisions:** ARCHITECTURE_CONSTITUTION (Estimation promoted to first-class, feeds EI), ADR-001 (event authority / determinism), ADR-007 (durable log), ADR-004 (determinism boundaries)
- **Rule observed:** implementation only — no redesign, no protocol/contract/invariant/ADR edits, no engine redesign, no application-logic migration, no commit.

---

## 1. Executive Summary

`nexus_estimation` is the deterministic **Estimation Foundation** — the single constitutional owner of quantitative execution assessment that Engineering Intelligence (EI) will later consume. Given **immutable facts** it produces an immutable, explainable `EstimationReport` bundling the five required estimates — **ComplexityEstimate, DurationEstimate, CostEstimate, ConfidenceEstimate, ResourceEstimate** — each with a value, a reasoning trace, its contributing factors, a confidence, and a deterministic identity.

It is a **pure function of (immutable signals, versioned model)**: no randomness, no clock in the scoring, no time-varying heuristic, no reasoning, **no LLM**, no runtime/skill/intent/plan/policy decision. Identical input → identical estimate → identical replay. Historical statistics enter only as **versioned inputs** (the `EstimationModel.version`). Durability is transparent through P1: each estimation records one `estimation.estimated` fact (the report embedded in the payload) so replay reconstructs every estimate after restart with no re-computation.

**No engine, protocol, contract, or invariant was changed.** Integration is additive DI (`build_estimation`). Estimation **estimates only**; the estimate-consuming *engineering decision* remains EI's (INV-02), and EI does not yet exist (guardrail-proven).

**New package — `nexus_estimation/`** (13 modules): `vocabulary`, `baseline` (the versioned model + historical stats), `model` (the five estimate value objects + report + inputs), `signals` (fact → signal extraction), `rules` (deterministic scorers), `confidence` (the confidence model), `engine`, `events`, `ids`, `observability`, `persistence`, `composition`, `__init__`.

**Changed — `pyproject.toml`**: added `nexus_estimation` to the package list (packaging only).

**Tests** — `tests/unit/nexus_estimation/` (6 files + fixtures) + `tests/integration/test_estimation_durable.py`.

> **Program-label note (sequencing, not a conflict).** The Engineering Program numbers P4 as *Repository Intelligence* and folds estimation into *P8 (Engineering Intelligence + Estimation)*. This task briefs P4 as the *Estimation Foundation*. This is a sequencing/label divergence, not a constitutional conflict: the Constitution explicitly **promotes Estimation to a first-class subsystem that feeds EI** ("PROMOTE … Estimation … to first-class … EI mathematically needs Estimation"; "Estimation/Cost Intelligence … feeds EI"), and building the deterministic foundation *before* EI is exactly what "EI needs Estimation" implies. Reported here rather than silently reconciled.

---

## 2. Constitutional Compliance

| Constitutional requirement | Status | How |
|---|---|---|
| Estimation is a first-class Operations-plane subsystem feeding EI | ✅ | `nexus_estimation` produces estimates EI consumes; owns no engineering decision. |
| Estimation owns only quantitative assessment (complexity/duration/cost/…) | ✅ | Produces exactly the five estimate types; makes no decision. |
| Estimate types are subsystem value objects, not new frozen contracts (INV-07) | ✅ | Estimates are `ValueObject`s (the `ValidationReport` pattern); the estimation contract is a declared void, not frozen — no second consumer exists yet. |
| One owner per decision (INV-02) | ✅ | Estimation computes; EI (later) commits the estimate into its engineering decision. Guardrail: only `nexus_estimation` constructs the estimate types. |
| Explainable, recorded outputs (INV-31/INV-17) | ✅ | Every estimate carries factors + reasoning trace; the report is recorded as a durable event. |
| Deterministic and replayable (Article IV, deterministic subset) | ✅ | Pure functions; no randomness; historical stats are versioned inputs. |
| Non-responsibilities held | ✅ | No runtime/skill selection, intent classification, scheduling, approval, recovery, validation, or LLM — proven by import-level guardrail. |

**Scope note (deliberate, constitutional).** The Constitution *permits* Estimation to reason through the determinism seam (Article IV names "Understand, Reason, and Estimation" as the reasoning sites; "Estimation may reason (recorded)"). This task scopes to the **deterministic foundation only** — a strict subset. Building the deterministic core first (what EI consumes) is consistent with the Constitution; the optional recorded-reasoning layer is deferred, not precluded.

**Boundary observation (no change made).** `nexus_planning/plan_builder.py` populates the frozen `Plan.complexity_estimates` **Struct** with structural plan-shape *counts* (`work_package_count`, `dependency_count`). That is descriptive metadata Planning legitimately owns about the plan it built — a **naming overlap**, not the quantitative complexity/duration/cost assessment this subsystem owns. Planning was left untouched ("Planning unchanged"); the guardrail targets the estimate *types*, which Planning does not construct. Estimation could later *consume* those counts as input signals.

---

## 3. ADR Compliance

- **ADR-001 (event authority / determinism):** estimates are recorded as `estimation.estimated` events; state (the stored report) is derived; the one captured-as-data value is the injected event timestamp (INV-17), never recomputed in scoring.
- **ADR-007 (durable persistence):** no estimation-specific durable code — the engine emits through the `InfrastructureContext` and persists through a reused `InMemoryRepository`; over `build_durable_infrastructure` both are durable. The report is embedded in the event payload, so replay reconstructs it.
- **ADR-004 (determinism boundaries):** Estimation sits on the deterministic side — coordination/accounting, not cognition; it invokes no model. This is precisely the platform's "guaranteed-deterministic" set.
- **ADR-008 (shadow migration):** untouched. Because estimation is deterministic and side-effect-free (given `persist=False`), it is directly shadow-adjudicable via P3 when it migrates.

---

## 4. Determinism Validation

- **Pure scorers** (`test_rules.py`, `test_confidence.py`): `score_complexity`/`estimate_duration`/`estimate_cost`/`estimate_resource`/`score_confidence` each return identical output for identical input; weighted-sum complexity is exact (`17.8` for the sample), bands monotonic.
- **Identical inputs → identical estimates** (`test_engine.py::test_determinism_identical_inputs_identical_estimates`): the full report (timestamp aside) is value-equal across runs.
- **No randomness / no reasoning** (`test_guardrails.py`): AST-level import check proves no `random`/`openai`/`anthropic`/runtime/policy import; `datetime` is imported **only** by `events.py` (the injected timestamp), never by the scoring modules.
- **Version stability** (`test_versioning.py`): same model version + signals → identical estimate and identity; a different model version → a different-but-deterministic result whose identity encodes the version; historical statistics change duration/confidence deterministically as **versioned inputs**.

---

## 5. Replay Validation

- **Replay reconstructs estimates from the log** (`test_estimation_durable.py::test_replay_reconstructs_estimates_from_the_log`): `EstimationReport.model_validate(event.payload["report"])` equals the original — full reconstruction without re-computation.
- **Identical estimates across restart** (`test_identical_estimates_across_restart`): a fresh engine over the reopened durable file produces the value-equal report (pure function of signals + model).
- **Version stable across restart** (`test_version_stable_across_restart`): the reopened engine's model version and report identity match.
- **Confidence reproducibility** (`test_confidence.py::test_confidence_is_reproducible`).

---

## 6. Durable Integration

- **Durable events** (`test_estimation_event_is_durable`): the `estimation.estimated` fact survives reopening the SQLite file, correlated (INV-39).
- Rides P1 unchanged — no `Durable*` estimation class; durability is a property of the injected `InfrastructureContext`.
- Reports persist through a reused `InMemoryRepository` (the validation pattern); over a durable context they ride the durable substrate.

---

## 7. Explainability

Every estimate satisfies the required shape (`test_engine.py::test_every_estimate_carries_the_required_shape`): a **value**, a **reasoning_trace** (e.g. `dependency_count: 4.0 * 2.0 = 8.0` … `complexity score = 17.8 -> band moderate`), **contributing factors** (`Factor(name, value, weight, contribution)`), a **confidence** in `[0,1]`, a **deterministic identity**, and the **model version**. The confidence model itself is explainable: `signal coverage = 6/6 = 1.0`, `sample adequacy = …`, `confidence = 0.6·coverage + 0.4·samples → band`.

---

## 8. Risks

| Risk | Severity | Note / mitigation |
|---|---|---|
| Default model weights are illustrative | Medium | They are **versioned inputs**; a change ships as a new model version, itself deterministic and replayable. Real weights/baselines attach when EI/Operations supply historical data (as versioned models). |
| `Plan.complexity_estimates` naming overlaps this subsystem | Low | Structural counts, not estimation-subsystem estimates; Planning untouched; guardrail targets the estimate types. Documented in §2. |
| Report carries a timestamp → report equality needs a fixed clock | Low | The five *estimates* are timestamp-free and fully deterministic; only the report bundle stamps recording time (INV-17, injected). Tests compare estimates and fixed-clock reports. |
| Estimation later gains recorded reasoning (the constitutional "half") | Low | Out of P4 scope; the deterministic core is a clean substrate the reasoning layer can extend without changing the estimate contract. |

**No constitutional conflict was discovered.** The one place evidence pressed against the task — Planning writing a `complexity_estimates` field — resolved to a naming overlap over structural counts, not an ownership violation; surfaced in §2 rather than silently changed.

---

## 9. Remaining Work Before Engineering Intelligence

EI can now consume estimates **without implementing estimation itself** — it imports `nexus_estimation` and calls `EstimationEngine.estimate(...)`. Outstanding, none blocking EI's construction:

1. **Calibrated models:** replace the illustrative default weights/baselines with data-derived, versioned models once Operations/Execution History supplies recorded statistics (the model is already the versioned-input seam).
2. **Signal enrichment:** wire real dependency-graph, repository-metric, and runtime-capability signals through `merge_signals` as those grounding sources (P4 Repository Intelligence, Operations) come online.
3. **EI consumption point:** EI's recorded decision embeds the `EstimationReport` (or its identity) as the estimate facet — an EI concern, not an estimation change.
4. **Optional recorded-reasoning layer:** the constitutional "estimation may reason (recorded)" extension, if ever needed, attaches behind the same value-object contract.

**Verdict:** P4 is functionally complete. `nexus_estimation` is the single owner of quantitative execution assessment; every estimate is deterministic, explainable, versioned, and replayable; durability is transparent through P1; EI can consume estimates without owning estimation; and no engine, protocol, contract, or invariant was changed. **No commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_estimation` unit + durable integration | **39 passed** |
| Full v2 unit + integration sweep | **2486 passed**, 1 skipped, 1 pre-existing `--noconftest` fixture error (`test_state_machines.py` needs the v1 `db_session` conftest fixture — unrelated to P4) |
| Lint (`ruff`) on new package + tests | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent here) — a pre-existing environment condition; the v2 suites are plain pytest functions.
