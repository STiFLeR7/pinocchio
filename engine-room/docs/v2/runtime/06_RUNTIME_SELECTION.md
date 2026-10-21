# 06 — Runtime Selection

**Status:** design only. This is the pivotal document of the subsystem: it defines
**where runtime allocation happens** and how a set of upstream *candidates* becomes
exactly **one allocated runtime** bound to a Runtime Session. It describes a
**responsibility pipeline**, not an implemented algorithm — no ranking formula, no
provider logic, no code. It states explicitly **where Orchestration stops and the
Runtime Manager begins**, and where the boundary to the Execution Engine lies.

Read alongside: `01_RUNTIME_MANAGER.md` (the preparation pipeline, steps 2–8),
`05_RUNTIME_CAPABILITIES.md` (matching), `04_RUNTIME_REGISTRY.md` (health/availability),
`18_RUNTIME_GOVERNANCE.md` (policy/cost/isolation), `14_APPROVAL_CALLBACKS.md`
(approval pause), `02_RUNTIME_SESSION.md` (binding), `07_RUNTIME_LIFECYCLE.md`
(`Created → Prepared → Ready`), `15_RUNTIME_EVENTS.md` (the `runtime.*` facts emitted).

---

## 1. The one-sentence thesis

> Orchestration produces **candidates and policy**; the Runtime Manager performs the
> **final selection and allocation**. Selection narrows a candidate set to survivors;
> allocation reserves and binds exactly one survivor to the Runtime Session. **This is
> the layer where allocation lives** (INV-37). Execution does *not* live here — the
> handoff of a `Ready` session is the boundary.

This restates the platform spine one final time at the resource level: **RM PREPARES;
the Execution Engine PERFORMS.** Selecting and allocating a runtime is preparation.
Running work inside it is performance.

## 2. Where Orchestration stops and Runtime begins

The seam is a single field on the `RuntimeRequest` value object produced upstream:
`candidate_harness_refs`. The builder that produces it (Orchestration, Phase 5) is
explicit that it lists **candidates only, never a selection** (INV-37): it reads the
Harness Registry's `discover_by_capability` (candidates only — INV-37, owned by INV-36)
and emits the harnesses that *advertise* the required capabilities, sorted
deterministically. It allocates nothing, reserves nothing, and reads no live health
beyond advertised candidates.

```
        ORCHESTRATION (Phase 5)            │            RUNTIME MANAGER (Phase 7)
  ─────────────────────────────────────────┼─────────────────────────────────────────
  required_capability_refs                  │  resolve candidates → descriptors  (04)
  runtime_policy (declarative, from         │  match capabilities                (05)
      the Execution Strategy)               │  filter health / availability      (04/INV-36)
  discover_by_capability → candidates       │  apply policy: allowed/isolation/cost (18)
  EMITS: RuntimeRequest with                │  approval checkpoint (if required) (14)
      candidate_harness_refs (candidates    │  SELECT exactly one survivor       (this doc)
      ONLY — INV-37), runtime_policy        │  ALLOCATE: RESERVED → ALLOCATED    (this doc)
                                            │  BIND to the Runtime Session       (02)
  ──────────────────── candidates + policy ─┼─ selection + allocation ────────────────
                  (the request crosses the boundary by value/reference)
```

Everything left of the line is *eligibility*. Everything right of the line is
*decision and reservation*. Nothing upstream of the line ever names a provider, and
nothing downstream of the line ever re-derives policy.

> **Doc-07 wording tension (noted, not resolved here).** `07_RUNTIME_LIFECYCLE.md`'s
> upstream sibling in Phase 5 records (observation **O-9**) that the original
> Orchestration text says *"Orchestration assigns runtimes,"* while INV-37 and this
> phase say Orchestration produces **candidates only** and allocation is deferred to
> **this** layer. The contract — `RuntimeRequest.candidate_harness_refs`, "candidates
> only" — is unambiguous and is what this document binds to. The residual wording
> tension between "assigns" and "produces candidates" is analyzed in
> `ARCHITECTURE_REVIEW.md`; it is **not** resolved in this design doc.

## 3. The selection responsibility pipeline

Selection is a **funnel**: a candidate set enters and is narrowed, stage by stage,
until exactly one runtime is chosen and reserved. Each stage can only *remove*
candidates (or pause); none invents new ones. The funnel corresponds to steps 2–8 of
the preparation pipeline in `01_RUNTIME_MANAGER.md`.

```
   candidate_harness_refs  (from Orchestration — candidates only, INV-37)
            │
            ▼  (A) RESOLVE      candidate refs → Runtime Descriptors via the Registry view (04)
            │
            ▼  (B) MATCH        keep candidates whose advertised caps ⊇ required caps (05)   → ELIGIBLE
            │
            ▼  (C) HEALTH       drop unavailable/unhealthy descriptors (Registry / INV-36)   → REACHABLE
            │
            ▼  (D) POLICY       drop runtimes disallowed by governance / isolation / cost (18) → PERMITTED
            │
            ▼  (E) APPROVAL     if policy requires it: PAUSE → wait → resume (ADR-004, 14)
            │
            ▼  (F) SELECT       choose exactly ONE from the survivors, deterministically (this doc)
            │
            ▼  (G) ALLOCATE     RESERVED → ALLOCATED in ResourceAllocationState (this doc)
            │
            ▼  (H) BIND         attach the allocated runtime to the Runtime Session (02)
            │
            ▼  → Prepared → Ready (07)   then handoff to the Execution Engine (boundary)
```

If the survivor set is **empty** at any stage after (A), there is no runtime to
allocate: RM does not improvise, lower a requirement, or pick a non-candidate. It
short-circuits to a typed error (`11_ERROR_MODEL.md`) and `runtime.failed` (`15`), and
the session goes `Created → Failed → Destroyed` (`07`). No silent default — ever.

### Stage table

| Stage | Input set | Removes candidates that… | Authority | Output set | Event (`15`) |
|---|---|---|---|---|---|
| A Resolve | candidate refs | cannot be resolved to a Registry descriptor | Registry view (`04`) | RESOLVED | `runtime.candidates_resolved` |
| B Match | RESOLVED | do not advertise every required capability | Capabilities (`05`, INV-32) | ELIGIBLE | `runtime.capabilities_matched` |
| C Health | ELIGIBLE | are not `AVAILABLE`/reachable per the Registry | Registry / INV-36 (`04`) | REACHABLE | (filter; see §6) |
| D Policy | REACHABLE | are disallowed by governance, isolation, or cost policy | Governance (`18`) | PERMITTED | (decision recorded; `18`) |
| E Approval | PERMITTED | — (no removal; a *gate*, not a filter) | Approval (`14`, ADR-004) | PERMITTED | `runtime.waiting_approval` / `runtime.resumed` |
| F Select | PERMITTED (survivors) | — (chooses one) | RM (this doc) | the chosen runtime | (folded into `runtime.allocated`) |
| G Allocate | the chosen runtime | — | RM + Registry capacity (`04`) | an allocation | `runtime.allocated` |
| H Bind | the allocation | — | Runtime Session (`02`) | a bound session | `runtime.session_created` precedes; `runtime.prepared` follows |

## 4. (A–B) Candidates → eligible: capability matching

Candidates are *advertised as capable*; they are not yet *confirmed as eligible*.
Matching (`05_RUNTIME_CAPABILITIES.md`) confirms each candidate's **advertised
capabilities** are a superset of the manifest's **required capabilities**. Per
**INV-32**, this comparison is entirely **provider-independent**: it compares abstract
capability references (the same `required_capability_refs` Orchestration used to build
the candidate set), never provider names. A candidate that advertised a capability it
no longer satisfies, or that resolves to a descriptor whose advertised set has changed,
is dropped here — not assumed. The survivors are the **ELIGIBLE** set.

This stage is where the contract is honored that **a Work Package never selects its
own runtime (INV-21)**: the package contributes *requirements*; matching consumes those
requirements against candidate descriptors; the package never names or ranks a runtime.

## 5. (C) Eligible → reachable: health & availability

Matching proves a runtime *could* do the work; it does not prove the runtime is *up*.
**The Harness Registry owns availability and health (INV-36)**, and RM **reads** that
state — it never duplicates or re-owns it. The Registry view (`04`) exposes each
descriptor's `availability` (the `ResourceAvailability` projection:
`AVAILABLE / BUSY / RESERVED / OFFLINE / MAINTENANCE / FAILED / UNKNOWN`) and `health`.

RM keeps only candidates the Registry reports as reachable (effectively `AVAILABLE`,
within whatever tolerance `04` defines for `UNKNOWN`/transient states) and drops the
rest. Health is **read at intake and snapshotted** so a single preparation reasons over
a stable view (the determinism rule of `01` §5): the funnel does not re-poll mid-funnel
and contradict itself. The survivors are the **REACHABLE** set.

## 6. (D) Reachable → permitted: policy, isolation, and cost

Policy narrows *reachable* runtimes to *permitted* ones. All of it is **declarative**:
it arrives on the `RuntimeRequest` as `runtime_policy` (a `Struct` carried verbatim
from the Execution Strategy) plus governance policy resolved via `18`. **RM applies
policy; it never re-derives it** — RM is not allowed to decide *what* the policy should
be, only to honor what was already declared. This mirrors how every prior layer treats
the Strategy as authoritative.

| Policy lever | Source | Effect on the funnel | Owner |
|---|---|---|---|
| **Allowed runtimes** | governance policy (`18`) | remove any candidate not on the allow-list / on a deny-list | Governance |
| **Isolation requirement** | Strategy / governance | remove candidates that cannot satisfy the required isolation profile (`17`) | Governance + Security |
| **Cost ceiling** | `runtime_policy` (declarative) | remove candidates whose declared cost exceeds the ceiling | RM applies; Strategy declares |
| **Cost preference** | `runtime_policy` (declarative) | bias the *tie-break* among survivors (input to §8) — never re-derived | RM applies; Strategy declares |

**Where cost influences the decision.** Cost enters in two distinct ways, both
declarative. A **ceiling** is a *filter* (stage D): a candidate above the ceiling is
removed, exactly like a health failure. A **preference** is a *tie-break input* (stage
F, §8): among otherwise-equivalent survivors, a declared cost preference may order them.
RM **reads these from `runtime_policy` and applies them**; it never computes a cost
model, never prices a provider, and never overrides the declared ceiling. If cost data
is absent, RM treats the lever as unset — it does not invent one.

The survivors of stage D are the **PERMITTED** set. Policy *decisions* themselves (the
`PolicyDecision` set: `ALLOW / DENY / REQUIRE_APPROVAL / DELAY / ESCALATE /
REQUEST_INFORMATION`) are owned by governance (`18`); a `DENY` removes a candidate, a
`REQUIRE_APPROVAL` routes to stage E, and RM records the decision but never makes it.

## 7. (E) The approval checkpoint — before allocation

When governance policy returns `REQUIRE_APPROVAL` (or the Strategy's `ApprovalTaxonomy`
is `HUMAN_REVIEW` / `MULTI_STAGE` / `DEFERRED` rather than `AUTOMATIC`), an **approval
checkpoint sits between selection-eligibility and allocation**. This is a deliberate
ordering choice: **approval gates the commitment of a resource.** RM does not reserve
capacity, then ask permission; it pauses *before* spending the allocation.

Per **ADR-004**, there is a **single approval taxonomy**, and **RM PAUSES for approval;
it never DECIDES** an approval. At the checkpoint, RM:

- emits `runtime.waiting_approval` and moves the session toward the `Waiting` posture
  (the lifecycle handles this via `14`; note the session may still be in preparation,
  so the pause is expressed as the preparation analogue of `Waiting` per `07`/`14`);
- surrenders the decision to the approver through the approval-callback mechanism
  (`14_APPROVAL_CALLBACKS.md`) — RM depends on no UI;
- on **grant**, emits `runtime.resumed` and proceeds to stage F (Select);
- on **denial / timeout**, abandons the attempt cleanly: no allocation is made, and the
  session goes `Created/Prepared → Destroyed` directly (the "abandon before handoff"
  edge in `07`).

Approval is a **gate, not a filter**: it does not remove individual candidates; it
authorizes (or refuses) the act of allocating from the permitted survivors.

## 8. (F) Select exactly one — deterministically

After the funnel, one or more **survivors** remain. Selection chooses **exactly one**.
This document deliberately **does not** prescribe a ranking formula. It specifies the
**inputs** to the choice and **who owns the tie-break**, leaving the concrete ordering
to implementation within these constraints:

**Decision inputs (read-only, all already on the request or the descriptor):**

- the **survivor set** (PERMITTED, post-approval);
- declarative **preferences** from `runtime_policy` (e.g. cost preference, §6; any
  declared runtime preference order) — applied, never re-derived;
- the Registry's **deterministic ordering** of descriptors (the candidate set is
  produced sorted; `04` defines a stable order);
- the **prioritization** signal the Registry/descriptor exposes (`04`), if any.

**Tie-break responsibility & determinism.** When inputs leave two survivors equivalent,
the tie-break MUST be **deterministic and total** — a stable, well-defined order (e.g.
the Registry's canonical descriptor ordering) so that *given the same request and the
same Registry snapshot, RM selects the same runtime* (`01` §5). No clock, counter, or
randomness participates in selection. RM owns the tie-break rule; it does not delegate
the *final pick* to the runtime, the package (INV-21), or the operator (the operator may
*approve*, §7, but does not *choose* among survivors).

The chosen runtime is recorded as the runtime identity that the subsequent
`runtime.allocated` event carries.

## 9. (G) Allocate — reserve, then allocate

Selection names a runtime; **allocation commits it.** Allocation is tracked by the
shared `ResourceAllocationState` and moves through its states in order:

```
   AVAILABLE  ──reserve──▶  RESERVED  ──allocate──▶  ALLOCATED  ──(later, teardown)──▶  RELEASED
```

- **RESERVE** — RM claims the chosen runtime's capacity so a concurrent preparation does
  not double-book it. This is the commitment point: from here, the funnel's decision is
  binding for this attempt.
- **ALLOCATE** — the reservation is confirmed into a live allocation tied to the
  session. The allocation carries a deterministic **allocation id** (a pure function of
  the session id and the chosen runtime identity — `02` §3), so a replay reproduces the
  same allocation.
- **RELEASE** — *not* part of selection; it happens at teardown (`07` §6, `09`), on
  every path (success, cancel, fail), so capacity is **never leaked**. RM owns release
  exactly as it owns reserve/allocate.

`runtime.allocated` (`15`) is emitted with the session, runtime, allocation, and
allocation state. Capacity accounting is reconciled against the Registry (`04`); RM does
not invent a second capacity store (consistent with INV-36 and the "no second registry"
canon).

> **Boundary check (allocation lives here).** The reserve→allocate transition is the
> concrete reason this document is the home of allocation. Orchestration could not do
> it (it has only candidates and no commitment authority — INV-37); the Execution Engine
> must not do it (it receives an *already-allocated* runtime). Allocation is RM's, and
> only RM's.

## 10. (H) Bind — allocation into the session

The final selection act binds the allocation to the **Runtime Session** (`02`). The
session's `runtime_ref` now points at the allocated Runtime Descriptor and its
`allocation_ref` at the reservation record. With the binding in place the session has a
concrete runtime and can be configured (`Prepared`) and made `Ready` (`07`).

Selection's outputs onto the session (all by reference, never embedded — `02` §2):

| Session field | Set by selection to | Provenance |
|---|---|---|
| `runtime_ref` | the chosen, allocated Runtime Descriptor | Registry view (`04`) after stage G |
| `allocation_ref` | the reservation record | this document, stage G |

Order of facts, per `15`: `runtime.candidates_resolved` →
`runtime.capabilities_matched` → (`runtime.waiting_approval`/`runtime.resumed` if
gated) → `runtime.allocated`, with `runtime.session_created` marking the binding and
`runtime.prepared` following once configuration is rendered.

## 11. Where allocation ends and execution begins (the boundary)

Selection and allocation are the **last preparation acts that decide a resource.**
After binding, RM renders configuration (`Prepared`), passes readiness checks (`Ready`),
and **hands the `Ready` session to the Execution Engine.** Crossing that handoff:

| Concern | Side of the boundary | Owner |
|---|---|---|
| Produce runtime **candidates** | upstream of RM | Orchestration (INV-37) |
| Match capabilities, filter health, apply policy | inside RM | RM (`05`/`04`/`18`) |
| Pause for approval | inside RM | RM pauses; approver decides (`14`, ADR-004) |
| **Select one runtime** | inside RM | RM (this doc) |
| **Allocate (reserve → allocate)** | inside RM | RM (this doc, INV-37) |
| **Run the work in the allocated runtime** | downstream of RM | Execution Engine (Phase 8) |
| **Release the allocation** | inside RM, at teardown | RM (`07` §6) |

The Execution Engine never selects, never allocates, never releases. It receives a
runtime that RM already chose, reserved, allocated, and bound. **The handoff is the
boundary: allocation belongs to this layer; execution does not.**

## 12. Invariants and canon honored here

| Invariant / ADR | How this document honors it |
|---|---|
| **INV-37** Orchestration produces candidates; allocation is later | Allocation is performed **here**, from `candidate_harness_refs`; Orchestration only produced candidates |
| **INV-21** a Work Package never selects its runtime | Selection is RM's; the package contributes only requirements |
| **INV-32** capabilities are provider-independent | Stage B compares abstract capability refs; provider identity enters only at bind (stage H) |
| **INV-36** the Registry owns availability/health | Stage C **reads** Registry health; RM never duplicates or re-owns it |
| **ADR-002** registries & a Runtime is a `RUNTIME` Harness | Candidates and health come from the Registry view over the Harness Registry — no second store |
| **ADR-004** single approval taxonomy; RM pauses, never decides | Stage E uses the platform taxonomy and the `14` callback; RM pauses, the approver decides |
| **Determinism** (`01` §5) | Snapshotted health, declarative policy, total tie-break, deterministic allocation id ⇒ same inputs → same allocation |

## 13. Cross-references

- `01_RUNTIME_MANAGER.md` — the full preparation pipeline (this doc expands steps 2–8).
- `04_RUNTIME_REGISTRY.md` — candidate resolution, availability/health, ordering, capacity.
- `05_RUNTIME_CAPABILITIES.md` — capability matching (stages A–B).
- `18_RUNTIME_GOVERNANCE.md` — policy/isolation/cost levers and `PolicyDecision` ownership.
- `14_APPROVAL_CALLBACKS.md` — the approval pause mechanism (stage E).
- `02_RUNTIME_SESSION.md` — the binding the allocation attaches to (stage H).
- `07_RUNTIME_LIFECYCLE.md` — `Created → Prepared → Ready`, abandon-before-handoff, release at teardown.
- `15_RUNTIME_EVENTS.md` — `runtime.candidates_resolved`, `capabilities_matched`, `allocated`, `prepared`, `ready`, `released`.
- `ARCHITECTURE_REVIEW.md` — analysis of the doc-07 "assigns" vs. "candidates only" wording tension (O-9).
