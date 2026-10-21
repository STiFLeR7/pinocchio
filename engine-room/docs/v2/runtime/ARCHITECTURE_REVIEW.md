# Runtime Manager — Architecture Review

**Status:** design review only. This document evaluates the Phase 7 Runtime Manager
(RM) specification (`00`–`20`) for correctness, scalability, dependency direction,
architectural risk, failure modes, extensibility, and operational readiness. It
**modifies no ADR, contract, or invariant.** Where the existing Phase 0 architecture
should be *clarified* before Runtime implementation begins, that is recorded in §9 as a
**recommendation only** — nothing is applied.

The question this review answers: *is the Runtime architecture rigorous enough that an
implementation team could build it without making new architectural decisions, and does
it correctly support every present and future execution engine without compromise?*
**Conclusion: yes, with one clarifying amendment recommended (§9.1) and a small set of
bounded gaps (`20`) to settle during implementation.**

---

## 1. Correctness

The specification holds the platform's defining boundary — **prepare vs perform** — at
the final seam, exactly as every prior layer held *its* boundary:

| Prior boundary | Held by | Runtime analogue |
|---|---|---|
| decide work | Planning | RM never plans (`01` §3) |
| coordinate work | Orchestration | RM prepares one package at a time |
| compile work | Harness | RM allocates + sessions, never compiles |
| **perform work** | **Execution Engine (Phase 8)** | **RM hands off at `Ready`; never runs** |

Correctness rests on three load-bearing decisions, each consistent with the frozen
contracts:

1. **A "Runtime" is a Harness of category `RUNTIME`** (ADR-002 / doc 11). RM therefore
   reuses the existing Harness Registry as a *view* (`04`) rather than inventing a
   second registry — the single largest correctness win, because it keeps availability/
   health ownership in exactly one place (INV-36).
2. **`Completed` ≠ validated** (`07`, INV-20). RM marks the *process* ended and emits
   `runtime.completed`; Validation alone renders the success verdict from Evidence. This
   prevents the classic agent-framework error of treating "the tool exited 0" as "the
   work is done."
3. **Allocation, not execution, lives in RM** (`06`, INV-37). Orchestration produced
   *candidates only*; RM performs the final selection + allocation and then stops at
   handoff. This is the precise place the deferred Phase-5 responsibility (observation
   O-9) lands.

The lifecycle (`07`) is a closed state machine with an explicit legal-transition table
and fail-fast rejection of illegal transitions, mirroring the core state machine's
discipline. The event taxonomy (`15`) is the canonical `Event` envelope with
deterministic ids, idempotent consumption (INV-16), and timestamps-as-data (INV-17), so
session state is a pure projection (ADR-001) and RM is replay-correct and crash-safe by
construction.

**Verdict: correct.** No document contradicts a frozen invariant; the one wording
mismatch found is upstream, not in RM, and is addressed in §9.1.

## 2. Scalability

| Dimension | Assessment |
|---|---|
| **Many runtimes** | The Registry-view + capability model (`04`/`05`) scales by *capability*, not by enumerated providers; adding runtimes is O(1) on upstream layers (`19`). |
| **Many concurrent sessions** | The session model (`02`) is per-attempt and independent; allocation via `ResourceAllocationState` gives a natural concurrency/capacity accounting seam. **Caveat:** per-runtime concurrency limits, pooling, and quotas are *flagged but not designed* (`20` G-3) — a bounded implementation-time decision, not an architectural hole. |
| **High event volume** | Streaming (`08`) explicitly addresses backpressure/volume/truncation as design responsibilities and routes large output to artifact references rather than unbounded event payloads (`13`). Persistence limits remain an implementation tuning point (`20`). |
| **Distributed / multi-node RM** | Event-sourced state makes a multi-node RM *possible* (state is the log, not in-memory), but the topology is deferred (`20` G-6). The architecture does not preclude it. |

**Verdict: scalable in shape**, with concurrency/capacity and distribution explicitly
deferred as bounded gaps rather than left ambiguous.

## 3. Dependency direction

The specified direction is clean and one-way:

```
nexus_runtime → { nexus_core, nexus_infra }            (imports)
nexus_runtime consumes Harness/Orchestration OUTPUTS    (by value/reference)
nexus_runtime is imported by nothing upstream
provider code lives ONLY behind Runtime Adapters
```

This matches the acyclic, additive discipline every prior layer followed
(`00` §4). Two properties make it robust:

- **Capability-mediated coupling.** Upstream layers reference runtimes only by
  *capability* (INV-32/37), never by provider identity, so the dependency from
  "work" to "runtime" is inverted through the Registry/adapter boundary (`19`). This is
  what makes the open/closed claim (RM core closed, runtimes open) true rather than
  aspirational.
- **Infra reuse, not extension.** RM persists/emits only through the Phase 2 substrate
  and does not modify `nexus_infra` — the same constraint honored by Planning, Context,
  Orchestration, and Harness.

**Verdict: sound.** No cycle, no upstream knowledge of providers, no new persistence
mechanism.

## 4. Architectural risks

| # | Risk | Severity | Mitigation in the spec |
|---|---|---|---|
| R-1 | **Allocation-ownership wording mismatch** (doc 07 "Orchestration assigns runtimes" + `ResourceAllocationState` docstring "Orchestration-owned projection") vs INV-37 / RM-allocates. | **High (clarity)** | The runtime docs bind to INV-37 (candidates only; RM allocates) and flag the wording; §9.1 recommends a clarifying amendment. *No behavioral risk — the contracts (RuntimeRequest = candidates only) already enforce the correct semantics.* |
| R-2 | **Session/allocation lack a frozen core contract** (they are runtime-layer value objects, mirroring Phase-5 O-7/O-10). | Medium | Acceptable now (every layer shipped outputs this way first); §9.2 recommends a future contract-freeze pass if these objects must cross layers (Supervision, Recovery, the Execution Engine will read sessions). |
| R-3 | **Adapter contract is the single point of provider leakage** — a weak adapter boundary would leak provider specifics into RM core. | Medium | `03` defines the adapter as a *driver, never a decision-maker*, with a 9-concern contract and an 8-runtime conformance table; `17` pins per-runtime isolation. Enforcement is an implementation-review obligation. |
| R-4 | **"Completed vs validated" could be conflated** by a naive Execution Engine. | Medium | `07`/`15`/`13` repeatedly fix that `runtime.completed` = process ended; only Validation promotes Evidence Candidates → Evidence (INV-20). The seam is explicit. |
| R-5 | **Approval/timeout interplay** (a waiting approval that itself times out). | Low | `14` routes approval timeout through `10` (`runtime.timed_out`, `timeout_kind=approval`) → terminal, fail-closed (never implicit grant). |
| R-6 | **Secret leakage** through packages, events, logs, or artifacts. | High (security) | `17` mandates secrets by injected reference only, never embedded/printed, revoked at teardown; `08`/`13` require redaction. Consistent with the platform's `.env`-single-source / fail-closed rules. |

No risk is a *blocker*; R-1 and R-6 are the two to watch — R-1 is a documentation
clarification, R-6 is an implementation-discipline obligation the spec already mandates.

## 5. Failure modes

The error model (`11`) classifies failures (runtime-unavailable, allocation-failure,
execution-startup-failure, transport-failure, provider-failure, infrastructure-failure,
user-cancellation, timeout) and assigns each an owner and a downstream consumer
(Recovery). Three properties make the failure design strong:

- **Always reach `Destroyed`.** Every started session tears down on every path —
  allocation released, adapter cleanup run — so capacity and credentials never leak
  (`07` §6, `09`). A failing *cleanup* is itself a typed teardown error, surfaced not
  hidden.
- **Fail-fast, no silent correction.** Illegal transitions and unresolved
  policy/approval/credential states refuse the session rather than degrading into a
  running-but-wrong state (`07`, `17`, `18`).
- **RM stops at the boundary of recovery.** RM classifies and emits `runtime.failed` /
  `runtime.timed_out`; it never selects retry/rollback/abort — that is the future
  Recovery subsystem (`11`, `09`, `10`). This keeps the failure surface honest and the
  responsibility split clean.

**Verdict: robust and correctly scoped.** The one subtlety — whether a fired timeout
resolves to `Cancelled` or `Failed` — is resolved by "RM follows the declared
Strategy/governance classification; it never chooses on its own" (declaration ≠
evaluation, ADR-004), which is consistent with the canon.

## 6. Extensibility

`19` demonstrates that a new runtime requires **only** a new Adapter plus a Registry
registration — Planning, Context, Orchestration, and Harness provably do not change,
because they speak capabilities, not runtimes. The "insulation table" and the
walkthrough make the open/closed posture concrete and testable. Multi-adapter
versioning/coexistence and deprecation are addressed. This is the spec's strongest
section and directly satisfies the Phase-7 design goal of supporting unknown future
runtimes without redesign.

**Verdict: excellent.** The extensibility claim is structural (enforced by dependency
direction + capability mediation), not merely asserted.

## 7. Operational readiness

| Capability | Spec coverage |
|---|---|
| Observability | `16` — reuses the Phase 2 substrate; derived metrics/traces distinct from the authoritative event log; per-runtime health via the Registry (INV-36). |
| Security | `17` — per-runtime isolation profiles, secret-by-reference, least privilege, fail-closed, teardown revocation. |
| Governance/audit | `18` — Policy Engine evaluates / RM enforces; closed `PolicyDecision` set mapped to the runtime boundary; every allocation/approval/outcome is an immutable audited event. |
| Cancellation/timeout | `09`/`10` — graceful→forced escalation, four timeout kinds, declarative bounds RM enforces. |
| Streaming/progress/artifacts | `08`/`12`/`13` — runtime-independent, unknown-progress first-class, artifacts as Evidence Candidates by reference. |

**Gaps to operational completeness** are enumerated honestly in `20` (concurrency/
capacity, checkpoint-resume depth, streaming persistence limits, distributed RM,
Supervision-vs-RM boundary, cost-accounting source of truth). All are bounded
implementation-time decisions, not architectural unknowns.

**Verdict: operationally ready to implement**, contingent on settling the `20` gaps as
implementation tasks.

## 8. Cross-cutting consistency check

- **Vocabulary:** all 22 documents use the canon glossary (`00` §7); no document coined
  a competing lifecycle state or event name (verified during authoring — every `runtime.*`
  reference is a subset of `15`, every state a member of `07`).
- **Invariant attribution:** documents attribute invariants carefully and never assert a
  new invariant binding.
- **Boundary repetition:** "RM prepares; the Engine performs; Validation judges; Recovery
  recovers" is restated consistently across the streaming, progress, artifact, error,
  timeout, and governance docs — the spine never drifts.

## 9. Recommended Phase-0 clarifications (NOT applied)

> These are **recommendations**. No ADR, contract, or invariant is modified by this
> exercise. Apply (if at all) through the normal architecture-amendment process before
> Runtime implementation.

### 9.1 Clarify allocation ownership (recommended — high value, low risk)

**Observation.** Two upstream artifacts read as if Orchestration *allocates* runtimes:
- doc 07 (Orchestration) language: "Orchestration *assigns* runtimes."
- `nexus_core/contracts/enums.py` → `ResourceAllocationState` docstring: *"Resource
  allocation state (Orchestration-owned projection)."*

Both predate the Phase-5 decision (observation **O-9**) that **deferred allocation to a
later phase**, and both sit against **INV-37** (Orchestration produces *candidates
only*) and the shipped `RuntimeRequest` contract (`candidate_harness_refs`, candidates
only; no allocation field).

**Why it is not a behavioral bug.** The *contracts* already enforce the correct
semantics — Orchestration cannot allocate because it emits only candidates. The mismatch
is **wording**, not behavior. The runtime spec binds to the contract throughout (`06`).

**Recommendation.** A clarifying (non-semantic) amendment that states the division
explicitly:

> *Orchestration nominates runtime **candidates** and the governing **policy** (INV-37).
> The **Runtime Manager** performs the final **selection and allocation** from those
> candidates. `ResourceAllocationState` is owned by the **Runtime Manager**; Orchestration
> reads it as a projection where relevant.*

This touches doc 07 prose and one enum docstring. It changes **no** invariant (INV-37 is
already correct) and **no** behavior. Recommended **before** Runtime implementation so
the implementing team finds one consistent ownership story. **Do not edit the ADR in this
exercise.**

### 9.2 Decide whether Runtime Session / Allocation become frozen contracts (recommended — future)

Mirrors Phase-5 O-7/O-10. The Runtime Session and the allocation record currently ship
as runtime-layer value objects. The Execution Engine, Supervision, and Recovery will all
read sessions; if these objects must cross layers, a future contract-freeze pass should
ratify them. **Low urgency now; medium before Phase 8.** (`20` G-1.)

### 9.3 Consider a dedicated Registry phase (recommended — future)

Mirrors O-8/O-11. The concrete registries (Skill/Capability/Policy/Harness, and the
Runtime view) currently ship as reference implementations in consuming layers. A future
Registry phase (or a `nexus_infra` extension) could own them; RM would consume by
injection. **Low urgency.** (`20` G-10.)

## 10. Final assessment

| Axis | Rating | Note |
|---|---|---|
| Correctness | ✅ Strong | Boundary held; no invariant contradicted |
| Scalability | ✅ Sound shape | Concurrency/capacity deferred, bounded (`20`) |
| Dependency direction | ✅ Clean | Acyclic, capability-mediated, infra-reusing |
| Risk posture | ✅ Managed | R-1 (wording) + R-6 (secrets) are the watch items |
| Failure modes | ✅ Robust | Always-`Destroyed`, fail-fast, recovery-scoped-out |
| Extensibility | ✅ Excellent | New runtime = adapter + registration only |
| Operational readiness | ✅ Ready to build | `20` gaps are implementation tasks |

**The Runtime subsystem is fully specified architecturally.** A future implementation
team can build the Runtime Manager from `00`–`20` without making new architectural
decisions, provided the `20` gaps are taken as scoped implementation tasks and the §9.1
wording clarification is applied through the normal process. The execution boundary is
now designed with the same rigor as every layer preceding it.

**Phase 7 (architecture) complete. Implementation remains deliberately out of scope.**
