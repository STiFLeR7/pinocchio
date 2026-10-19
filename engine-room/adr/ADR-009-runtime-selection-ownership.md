# ADR-009 — Runtime Selection Ownership

- **Status:** Proposed (not ratified in this program; filed for a future decision)
- **Date:** 2026-07-21
- **Deciders:** Architecture Review Board (proposed)
- **Relates:** proposes a resolution to `docs/v2/P17_PRODUCTION_READINESS_REPORT.md` Phase 1 §1.1 finding **V3** and its follow-up item 7; depends on **ADR-002** (registry split; capability resolution returns candidates); consistent with **ADR-001** (events authoritative; determinism via captured data) and **ADR-004** (Policy evaluates; RM applies, never derives). Touches INV-02, INV-21, INV-23, INV-32, INV-36, and — centrally — **INV-37**.
- **Affected Action Points:** AP-005 (architecture-fitness/dependency test — the enforcement seam), AP-304 (capability resolution — candidates only), AP-402 (allocation), AP-207 (Harness/runtime registry). No new Action Point; this ADR reconciles ownership wording against already-shipped Action-Point implementations.

---

## 1. Context

INV-37 (as ratified in `docs/v2/99_ARCHITECTURAL_INVARIANTS.md:185`) reads:

> **INV-37 — Runtime selection is Orchestration's; capability resolution returns
> candidates only.** Resolution never selects a runtime; allocation never
> re-discovers capabilities. *(ADR-002.)*

ADR-002 §3 ("Capability Resolution ownership") is the same: resolution "returns
*candidates*. **Selection and allocation are Orchestration's** (AP-402)." The
`ARCHITECTURE_CONSTITUTION.md` restates it four times and never wavers: the
**COORDINATE** step (Orchestration) has among its responsibilities "**select the
runtime** (INV-37)" and emits "runtime allocations" (`ARCHITECTURE_CONSTITUTION.md`
COORDINATE section); the ownership table row reads "Runtime selection | Orchestration
| **INV-37**"; Planning "never selects the concrete runtime (Orchestration does —
INV-37)"; "Capability resolution must never select a runtime (INV-37 — Orchestration
selects)." At the *constitutional* layer the story is unambiguous and self-consistent:
**Orchestration selects and allocates.**

The **runtime subsystem's own design docs tell a different story** — deliberately, in
detail, and with a stated re-reading of INV-37:

- `docs/v2/runtime/06_RUNTIME_SELECTION.md` §1 (the subsystem's self-described
  "pivotal document"): *"Orchestration produces **candidates and policy**; the Runtime
  Manager performs the **final selection and allocation**. … **This is the layer where
  allocation lives** (INV-37)."* It reads INV-37 as "Orchestration produces candidates;
  allocation is later [in RM]," which is **not** what INV-37 as ratified says.
- `docs/v2/runtime/06_RUNTIME_SELECTION.md` §9 argues the point on architectural
  grounds: *"Orchestration could not do [allocation] (it has only candidates and no
  commitment authority — INV-37); the Execution Engine must not do it … Allocation is
  RM's, and only RM's."*
- `docs/v2/runtime/ARCHITECTURE_REVIEW.md` R-1 records the contradiction openly as a
  **High (clarity)** risk — "Allocation-ownership wording mismatch (doc 07
  'Orchestration assigns runtimes' + `ResourceAllocationState` docstring
  'Orchestration-owned projection') vs INV-37 / RM-allocates" — and §9.1 recommends a
  clarifying amendment stating "The **Runtime Manager** performs the final **selection
  and allocation**," on the belief that "INV-37 is already correct."

The implementation followed the **runtime docs**, not the Constitution. This ADR exists
because those two doc families now disagree about what INV-37 means, and the code has
picked a side.

## 2. Problem Statement

Runtime-selection ownership has drifted from Orchestration (where INV-37/ADR-002/the
Constitution place it) into the Runtime Manager and its Execution/Actuation trigger.
The drift is real in the call graph, and it has three distinct layers, each verified
against current source:

**(1) The selection funnel lives in the Runtime Manager, not Orchestration.**
The match → health → policy → choose funnel is `RuntimeSelector.select`
(`nexus_runtime/allocation.py:97-139`), constructed and driven by
`RuntimeManager` (`nexus_runtime/runtime_manager.py:72`, invoked at
`nexus_runtime/runtime_manager.py:153`). Orchestration produces candidates only and
**never imports `nexus_runtime`**: `RuntimeRequestBuilder`
(`nexus_orchestration/runtime_requests.py:44-98`) emits a `RuntimeRequest` carrying
`candidate_harness_refs` and `runtime_policy` and stops; `OrchestrationService`
(`nexus_orchestration/orchestrator.py:78-143`) is a pure structure-builder that
persists requests and returns — it has no run-loop and no path to a selector.

**(2) The trigger sits in Execution/Actuation, not Orchestration.**
Nothing in Orchestration calls the Runtime Manager. The only caller of
`RuntimeManager.prepare` is `RuntimeDispatcher.dispatch`
(`nexus_execution/actuation/dispatch.py:90-94`), which is driven by the
`ExecutionActuator` wave-loop (`nexus_execution/actuation/actuator.py:208`). So the
Constitution's COORDINATE responsibility to "drive the work through runtimes" is
realized inside the ACT step (Actuation). Actuation *does* reuse Orchestration's
readiness coordinators via `GraphWalker` (`nexus_execution/actuation/actuator.py:79`),
so *readiness* decisions remain Orchestration's — but the act of triggering runtime
selection is Execution's.

**(3) The code quietly redefines sole ownership as joint ownership.**
`nexus_execution/actuation/dispatch.py:7` asserts in its own docstring that
"selection/allocation stays Orchestration+Runtime's — INV-37," and
`nexus_execution/actuation/dispatch.py:65` repeats "Selection/allocation stays the
Manager's (INV-37)." The first phrasing invents a *joint* ownership that INV-37 does
not grant and INV-02 forbids; the second correctly names RM as sole owner. The two
sentences in one file disagree with each other.

**Why the drift exists (grounded in the docs, not speculation).** This is not an
accident of wiring — it is a deliberate subsystem-design decision that was never
propagated back up to the constitutional layer. The runtime designers concluded (doc 06
§9) that *allocation* — reserve capacity against the live Registry, then bind exactly
one survivor to a Runtime Session — is inherently a runtime-facing act that Orchestration
"could not do," and folded *selection* in with it because both consume the same
snapshotted Registry health view (doc 06 §5) and feed the same reserve→allocate step.
They then re-read INV-37 as "candidates only" for Orchestration and built accordingly.
Orchestration was, in turn, built as a stateless structure-builder with no selector and
no driver loop; Execution/Actuation supplied the run-loop because that is where nodes
are actually driven through runtimes at execution time. The constitutional documents
(INV-37, ADR-002, the Constitution) were simply never amended to match the design that
was chosen and shipped. `ARCHITECTURE_REVIEW.md` §9.1 flagged exactly this and asked for
the amendment "before Runtime implementation"; the amendment never happened, and the
implementation landed against the un-amended invariant.

The consequence for GA: P17 lists INV-37 as one of two unresolved constitutional
violations (`P17` GA checklist item 1: "✗ — 2 of 3 remain (V1 entrypoint, V3 INV-37
ownership)"). Until the ownership is settled in one direction, the platform's own
invariant set is internally inconsistent, and an architecture-fitness test cannot be
written that the code passes without first deciding what "correct" is.

## 3. Decision (Proposed)

> **PROPOSED: Ratify the Runtime Manager as the single owner of runtime *selection*
> and *allocation*, and correct INV-37 (and its restatements in ADR-002 §3, the
> Constitution's COORDINATE step and ownership table, and the `ResourceAllocationState`
> docstring) to the division the runtime design docs already specify: Orchestration
> nominates runtime **candidates** and the governing **policy**; the Runtime Manager
> performs the **final selection and allocation** from those candidates. Execution/
> Actuation *triggers* preparation but *decides* nothing about which runtime is chosen.**

This is Alternative A below, and it is the recommended alternative (§4). It is framed as
**proposed**, not accepted: this program only documents and recommends; ratification is a
future Architecture Review Board decision.

Under the proposed decision the single-owner assignment becomes:

| Decision | Owner (proposed) | Was (INV-37 as written) |
|---|---|---|
| Nominate runtime **candidates** (capability → advertising harnesses) | Orchestration (AP-304 / AP-402 request stage) | Orchestration |
| Carry the declarative **runtime policy** | Orchestration (from the Execution Strategy) | Orchestration |
| **Select** exactly one survivor (match→health→policy→choose) | **Runtime Manager** | Orchestration |
| **Allocate** (reserve → allocate → bind to Runtime Session) | **Runtime Manager** | Orchestration |
| **Trigger** runtime preparation for a ready node | Execution/Actuation (mechanical run-loop; no decision) | — |
| Own **readiness** (which nodes are ready now) | Orchestration coordinators (reused by Actuation via `GraphWalker`) | Orchestration |

The "joint ownership" phrasing at `dispatch.py:7` is a defect against INV-02 and is
corrected to name RM as the sole selection/allocation owner; Execution's role is
downgraded in prose to "invokes preparation," which is what the code already does.

## 4. Alternatives Considered

**A. Ratify current Runtime-Manager ownership as correct; correct INV-37's wording.**
Amend INV-37 (and the three restatements + one enum docstring) to say Orchestration
nominates candidates + policy and the Runtime Manager selects + allocates. No production
*logic* moves. *This is the recommended alternative.* It matches the runtime subsystem's
own detailed, deliberate design (`06_RUNTIME_SELECTION.md`, `01_RUNTIME_MANAGER.md`,
`ARCHITECTURE_REVIEW.md` §9.1), respects the well-grounded argument that allocation is
inherently runtime-facing (doc 06 §9), and restores a single owner per decision
(INV-02) by replacing the `dispatch.py` "joint ownership" phrasing with "RM selects and
allocates; Actuation only triggers." The only defect it must not leave standing is the
imprecise joint-ownership language.

**B. Relocate the actual selection logic into Orchestration to match INV-37 as written.**
Move `RuntimeSelector` into `nexus_orchestration`, thread the Harness Registry view and
a reservation ledger into Orchestration, have Orchestration emit an *assignment* (the
chosen runtime) on the `RuntimeRequest` instead of `candidate_harness_refs`, strip the
funnel from `RuntimeManager` (RM would bind an already-chosen runtime), and rewire
`RuntimeDispatcher` to consume an assignment. *Rejected.* Two grounded objections:
(i) **Architecture** — doc 06 §9's argument is sound: reserve-against-live-capacity and
bind-to-a-Runtime-Session are runtime-facing operations. Giving Orchestration a live
capacity ledger and session-binding authority duplicates RM's runtime-facing role and
breaks the "RM prepares; Orchestration coordinates" boundary — trading one INV-37 problem
for an INV-36/boundary problem. If instead selection moves to Orchestration but allocation
stays in RM, selection would run against candidate *references* without the live/snapshotted
health that RM reads at intake (doc 06 §5) — a *worse* decision made with less information.
(ii) **Cost** — this relocates a decision point across three subsystems and inverts the
shipped `RuntimeRequest` contract (candidates → assignment), which is close to a frozen
seam. High blast radius for a wording problem.

**C. Do nothing / defer.** Leave INV-37 as written and the code as built. *Rejected.* It
preserves a live contradiction between the constitutional layer and both the runtime
design docs and the implementation, keeps the `dispatch.py` self-contradiction, and
leaves P17 GA checklist item 1 permanently "✗." No architecture-fitness test can be
written that both encodes INV-37-as-written and passes. Deferral is only acceptable as an
explicit, dated "not before milestone N" note, not as a silent status quo.

## 5. Trade-offs

- **Gain (A):** the constitutional layer, the runtime design docs, and the code tell one
  consistent story; INV-02's single-owner rule is honored (RM owns selection+allocation;
  Orchestration owns candidate nomination + readiness; Execution owns only the trigger);
  the change is almost entirely documentation, so blast radius is minimal and reversible;
  the strong architectural argument that allocation is runtime-facing is preserved.
- **Cost (A):** an invariant is amended to match the implementation ("the code won"),
  which must be justified rather than rubber-stamped — the justification is that the
  *subsystem design* (doc 06) deliberately chose RM-ownership and the *constitutional*
  wording, not the design, is the stale artifact. One non-behavioral code touch (the
  `ResourceAllocationState` docstring) and one docstring correction (`dispatch.py`) are
  required so no in-tree comment still asserts the old ownership.
- **Trade-off vs. B:** B would let INV-37 stand verbatim, at the price of moving a
  decision point across subsystems and weakening a real architectural boundary. A keeps
  the boundary and moves words. The trade is "amend one invariant" (A) vs. "relocate a
  runtime-facing decision and invert a near-frozen contract" (B).

## 6. Consequences

- **INV-37** is reworded (proposed) to: *"Orchestration nominates runtime candidates and
  the governing policy; the Runtime Manager performs the final selection and allocation.
  Capability resolution returns candidates only; resolution never selects a runtime;
  allocation never re-discovers capabilities."* Its cross-references (ADR-002, doc 06)
  become mutually consistent.
- **ADR-002 §3** and the **Constitution's** COORDINATE step + ownership-table row
  ("Runtime selection | Orchestration") are amended to split "candidate nomination"
  (Orchestration) from "selection + allocation" (Runtime Manager). The Constitution's
  "Resource … → Orchestration" flow is reframed: Orchestration *reads* allocation state
  as a projection; RM *owns* it.
- **`nexus_core/contracts/enums.py`** `ResourceAllocationState` docstring changes from
  "Orchestration-owned projection" to "Runtime-Manager-owned" (per
  `ARCHITECTURE_REVIEW.md` §9.1) — non-behavioral.
- **`nexus_execution/actuation/dispatch.py`** docstring (`:7`) is corrected from
  "selection/allocation stays Orchestration+Runtime's" to name RM as sole owner and
  Actuation as trigger-only — non-behavioral, and it removes the INV-02 smell.
- **AP-005 architecture-fitness test** gains a rule set that pins the ratified ownership
  (see §8), so the resolved state cannot silently re-drift.
- **No `build_*` composition signature and no frozen contract changes.** The
  `RuntimeRequest` "candidates only" contract is *unchanged* — it was already correct
  under the proposed decision.

## 7. Risks

- **Implementation-risk estimate for the recommended Alternative A: LOW.** Reasoning: no
  production control flow or logic relocates; the runtime funnel already sits in RM and
  already produces the ratified behavior. The change is (a) documentation wording in four
  places, (b) two non-behavioral comment/docstring edits, and (c) one additive
  architecture-fitness test. There is no data migration, no contract change, no cutover.
  The single way to get it wrong is to reword an invariant while leaving a stale
  restatement or in-tree comment behind — mitigated by the grep-based fitness rule in §8
  that fails if any doc/comment still asserts Orchestration-owned selection.
  - *For contrast, Alternative B's implementation risk is HIGH* (moves a decision point
    across three subsystems, inverts a near-frozen contract, and weakens the RM boundary),
    and *Alternative C's risk is LOW effort but HIGH standing architectural-debt* (a
    permanent internal contradiction and a permanent GA blocker).
- **R1 — reviewer reads "amend the invariant" as "the code is allowed to win."**
  *Mitigation:* the ADR record shows the *subsystem design* (doc 06, dated before
  implementation) chose RM-ownership deliberately and `ARCHITECTURE_REVIEW.md` §9.1 asked
  for exactly this amendment; the stale artifact is the constitutional wording, not the
  design. This is reconciliation to the considered design, not capitulation to an accident.
- **R2 — residual "joint ownership" language survives somewhere.** *Mitigation:* §8's
  fitness rule greps the tree for INV-37 assertions and fails on any that name
  Orchestration (or "Orchestration+Runtime") as the selection/allocation owner.
- **R3 — a future change lets Orchestration import `nexus_runtime` and select directly,
  re-drifting toward B by accident.** *Mitigation:* the dependency test already forbids
  `nexus_orchestration → nexus_runtime`; §8 makes that forbiddance explicitly an INV-37
  guard so its purpose is legible.

## 8. Validation Strategy

Tests that would prove Alternative A is correctly realized (all extend AP-005's
architecture-fitness / dependency suite; all are static or unit-level, none behavioral):

- **Selection lives only in Runtime.** Assert `RuntimeSelector` (and any match→health→
  policy→choose funnel) is defined and constructed only within `nexus_runtime`; grep-fail
  if `nexus_orchestration` or `nexus_execution` constructs a selector or ranks candidates.
- **Orchestration stays candidates-only.** Assert `nexus_orchestration` does **not** import
  `nexus_runtime` (dependency test, already present — relabel it an INV-37 guard), and that
  `RuntimeRequest` still carries `candidate_harness_refs`/`runtime_policy` and no
  chosen-runtime/allocation field.
- **Single trigger seam.** Assert the only caller of `RuntimeManager.prepare` is the
  Runtime dispatch seam (`nexus_execution/actuation/dispatch.py`), so the trigger point is
  one, legible, and mechanical — not scattered decision-making.
- **No stale ownership assertion.** Grep the docs and in-tree docstrings/comments for
  INV-37 claims; fail if any names Orchestration (or "Orchestration+Runtime") as the
  *selection* or *allocation* owner after the amendment.
- **Determinism unchanged (regression).** The existing runtime selection determinism tests
  (same intakes + same Registry snapshot ⇒ same chosen runtime, allocation id, event
  stream — doc 06 §12) must still pass unchanged; this ADR must move zero behavior.
- *(If Alternative B were ever chosen instead)* the mirror tests would flip: selector
  constructed in `nexus_orchestration`, `RuntimeRequest` carries an assignment, RM binds a
  pre-chosen runtime and constructs no selector — plus a new test that Orchestration's
  selection reads live Registry health, since it would no longer inherit RM's intake snapshot.

## 9. Migration Considerations

Sequenced, additive, and — for the recommended Alternative A — free of any production
logic relocation. Each step is independently revertable.

1. **Ratify ADR-009** (Proposed → Accepted) at the Architecture Review Board. No code.
2. **Amend INV-37** in `docs/v2/99_ARCHITECTURAL_INVARIANTS.md` to the §6 wording. Doc-only.
3. **Reconcile the restatements:** ADR-002 §3 (add a "superseded on ownership wording by
   ADR-009" note rather than rewriting a ratified ADR in place), and the Constitution's
   COORDINATE step, ownership table row, and "Resource → Orchestration" flow. Doc-only.
4. **Correct the two in-tree assertions** (non-behavioral): `ResourceAllocationState`
   docstring in `nexus_core/contracts/enums.py` ("Runtime-Manager-owned"), and the
   `dispatch.py` docstring (RM sole owner; Actuation triggers). These are the *only* file
   edits under production paths, and neither changes behavior.
5. **Land the AP-005 fitness rules** from §8 so the resolved ownership is enforced and
   cannot silently re-drift. Additive test code only.
6. **Confirm zero behavioral delta:** run the full runtime + orchestration + actuation +
   integration suites; they must pass unchanged (this ADR moves words and tests, not logic).

*If Alternative B were chosen instead*, the migration is materially larger and is called
out here so the cost asymmetry is explicit: relocate `RuntimeSelector` into
`nexus_orchestration`; thread a Harness Registry view + reservation ledger into
Orchestration; change `RuntimeRequest` from candidates to an assignment (a
near-frozen-contract change requiring the INV-07 amendment process); reduce `RuntimeManager`
to binding a pre-chosen runtime; rewire `RuntimeDispatcher` to consume the assignment; and
add live-health access to Orchestration's new selection path. Each step is behavioral and
must be shadowed/tested against the current behavior before cutover — i.e. it is a genuine
code migration, not a documentation reconciliation.

## 10. Recommendation

**Recommend Alternative A.** Grounded in constitutional principles and practical cost:

- **INV-02 (one owner per decision / one responsibility per layer).** The live defect is
  not "RM selects" — it is the `dispatch.py:7` phrase that makes selection *jointly*
  Orchestration's and Runtime's. A restores a single owner cleanly (RM selects+allocates;
  Orchestration nominates+coordinates; Execution triggers). B also restores a single owner
  but by moving the owner; A restores it by naming the owner the code already uses.
- **INV-37 itself and the runtime design docs.** INV-37's *intent* — resolution returns
  candidates, one owner selects, allocation never re-discovers — is fully honored by A; only
  the *identity* of the selecting owner changes to match the subsystem design that was
  deliberately authored (doc 06) and shipped. The stale artifact is the constitutional
  wording, and `ARCHITECTURE_REVIEW.md` §9.1 already asked for precisely this correction.
- **The Constitution's Orchestration/Runtime boundary.** "RM prepares; the Execution Engine
  performs" is the platform spine. Selecting and allocating a runtime is preparation, and
  allocation (reserve against live capacity, bind to a Runtime Session) is intrinsically
  runtime-facing (doc 06 §9). A keeps that boundary intact; B perforates it by handing
  Orchestration a runtime-facing capacity ledger and binding authority.
- **Practical cost.** A moves ~0 lines of production logic (four doc edits, two
  non-behavioral comment edits, one additive test). B relocates a decision point across
  three subsystems and inverts a near-frozen contract. For a defect whose essence is
  "two documents disagree about a word," the proportionate fix is to fix the word and lock
  it with a test — not to relocate working, deterministic, well-tested code.

The one non-negotiable within A: do not stop at rewording INV-37. The `dispatch.py`
joint-ownership sentence and the `ResourceAllocationState` docstring must be corrected in
the same change, and the AP-005 fitness rules must land, or the contradiction simply moves
from the invariant into the code comments.

## 11. References

- `adr/ADR-002.md` (registry split; capability resolution returns candidates), `adr/ADR-008-shadow-migration.md` (structural pattern followed here).
- `docs/v2/99_ARCHITECTURAL_INVARIANTS.md` (INV-02, INV-21, INV-23, INV-32, INV-36, **INV-37**).
- `docs/v2/ARCHITECTURE_CONSTITUTION.md` (COORDINATE step; ownership table; Orchestration/Runtime boundary).
- `docs/v2/runtime/06_RUNTIME_SELECTION.md` (the subsystem's selection/allocation design — the RM-ownership reading of INV-37), `docs/v2/runtime/01_RUNTIME_MANAGER.md`, `docs/v2/runtime/ARCHITECTURE_REVIEW.md` (R-1, §9.1 — the flagged wording mismatch and its recommended amendment).
- `docs/v2/P17_PRODUCTION_READINESS_REPORT.md` (Phase 1 §1.1 finding **V3**; GA checklist item 1; follow-up item 7).
- Source (verified current): `nexus_orchestration/runtime_requests.py:44-98`, `nexus_orchestration/orchestrator.py:78-143`, `nexus_runtime/allocation.py:97-139`, `nexus_runtime/runtime_manager.py:72,153`, `nexus_execution/actuation/dispatch.py:7,65,90-94`, `nexus_execution/actuation/actuator.py:79,208`.
