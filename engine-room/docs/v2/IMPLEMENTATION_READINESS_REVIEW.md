# Nexus — Implementation Readiness Review

Status: **Independent readiness gate before the multi-month implementation era.** The Constitution and
Migration Blueprint are treated as frozen. This review answers exactly one question:

> **Can a team execute the Migration Blueprint without making new architectural decisions?**

Where the answer is no, this document points to the **exact source of the remaining ambiguity** (file,
contract, or stage). It designs nothing, changes nothing, and recommends no roadmap change unless the
evidence is strong.

**Method & integrity note.** Findings were verified from source during this review, and where source
contradicts a *prior* Nexus document — including my own Constitution and Blueprint — **source wins and the
prior claim is corrected here.** One such correction is material and improves readiness (Policy Engine);
two others are material and reduce it (durable-substrate integration; flag/shadow infrastructure).

---

## Executive Summary

**Verdict: APPROVED WITH CONDITIONS.** Roughly two-thirds of the year's work is genuinely ready to start
tomorrow against stable architecture. But **five bounded conditions** must be resolved before their
dependent stages, and until they are, a team *would* be forced to invent architecture at four specific
points. None is large; all are nameable; that is why this is a conditional approval, not NOT READY.

**What is genuinely ready (start now, no new architecture):**
- The **reasoning/execution spine** — Context, Plan, Coordinate, Execute, Validate, Recover, Reflect,
  Learn — is built, tested, and constitutional. Reshaping/wiring it needs no new decisions.
- **Policy Engine.** *Correction of a prior claim:* the Constitution and Blueprint asserted the Policy
  Engine "has no design corpus / is a void." **This is false.** `contracts/policy.md` is a **complete
  frozen contract** (closed decision set {Allow, Deny, RequireApproval, Delay, Escalate,
  RequestInformation}; structured predicate-tree conditions; deterministic conflict resolution
  Specificity→Priority→Version→Default; lifecycle Registered→Validated→Enabled→Disabled; fail-closed
  default) and it cites a numbered design doc `docs/v2/20_POLICY_ENGINE.md`. The Policy Engine is **ready
  to implement** — what is missing is the *package*, not the *architecture*.
- **Core object contracts** are frozen and sufficient for their subsystems: `goal.md` (178 lines),
  `intent.md` (170), `skill.md` (169), `knowledge.md` (216), `policy.md` (242), plus `plan`, `work_package`,
  `execution_graph`, `execution_strategy`, `observation`, `artifact`, `checkpoint`, `event`, `capability`,
  `resource`.

**The four points where a team would still invent architecture (the conditions):**

1. **Stage 1 "durable substrate" hides two unresolved decisions.** Verified: v2's `Repository`,
   `EventStore`, and `UnitOfWork` protocols (`nexus_core/persistence/interfaces.py`) are **synchronous**;
   v1's store (`nexus/memory/manager.py`) is **async** (`AsyncSession`). Worse, **v1 is CRUD/state-
   authoritative while v2 is event-sourced** (INV-13/14). "Reuse v1's DB behind v2's Repository protocol"
   (Blueprint Stage 1 / ADR-007) therefore requires two undesigned decisions: (a) the sync/async boundary,
   and (b) which store is *authoritative* — and a naive binding **violates INV-13** (the event log is the
   single source of truth). This is the Blueprint's "lowest-cost first move," and it is the least
   specified.

2. **The flag/shadow-mode infrastructure the whole integration depends on does not exist and is
   unspecified.** The Blueprint's Strangler strategy rests entirely on "shadow mode" and "feature flags"
   (Stages 3–8). No flag system exists in the repo, and neither the Constitution nor the Blueprint defines
   where flags live, how a shadow decision is **recorded as an event** (required by INV-39), or how
   flag-gated divergence is correlated. A team must invent this cross-cutting mechanism before Stage 3.

3. **Estimation is a genuine void.** No `estimation` contract, no design doc, no model for complexity /
   duration / cost. Engineering Intelligence's output and the Operations plane both depend on it. Building
   EI "completely" is blocked on inventing this model.

4. **The Operations plane is genuinely undesigned.** No numbered doc, no contract, no metrics model
   (confirmed: `docs/v2/` has 20_POLICY_ENGINE, 21_CAPABILITY, 22_RESOURCE, 23_EVENT, 24_STATE,
   25_CHECKPOINT, 26_REFLECTION — but **no Operations doc**). Stage 7 cannot start without one.

Plus a fifth, lower-severity condition: **four output contracts are unfrozen** (`engineering_strategy`,
`repository_understanding`, `interaction`, `environment`/`session`) — their subsystems can be *prototyped*
but not *finished* until the shapes are frozen (ADR-010, per INV-07).

**Why APPROVED WITH CONDITIONS and not NOT READY:** the conditions are bounded, identified, and mostly
*downstream*. Stages 0, 2 (Policy — ready), 4 (promote prototypes), and the EI/Intent *core* can begin
immediately. The conditions block Stages 1, 3, 5-estimation, and 7 — which are weeks-to-months out —
giving ample time to resolve them in parallel. **Five engineers can be productive for most of the year;
they cannot go the *whole* year without ~3–4 additional small foundational artifacts** (the persistence-
integration ADR, a flag/shadow spec, an Estimation model, an Operations doc). Naming those precisely is
this review's job, and it is done below.

---

## 1. Blueprint Executability (per stage)

| Stage | Rating | Why |
|---|---|---|
| **0 — Ratify (docs + ADR-005/006)** | **Fully specified** | Documentation and naming only; ADR-005/006 are reconciliations the invariants already support. Nothing to invent. |
| **1 — Durable substrate (ADR-007)** | **Ambiguous** | Two undesigned decisions: sync (v2 protocols) vs async (v1 store); and event-sourced-authoritative (INV-13/14, v2) vs CRUD-authoritative (v1). Naive binding violates INV-13. The Blueprint calls this "no behavior change," but the authority model *is* a behavior/architecture decision. **The load-bearing first stage is the least specified.** |
| **2 — Policy Engine (ADR-006)** | **Mostly specified** | `contracts/policy.md` + `20_POLICY_ENGINE.md` fully specify the object, decision set, and conflict algorithm. Gap: some named attributes (`cost_estimate`) depend on Estimation (void, Condition 3); the engine is buildable with the available attributes and grows additively. |
| **3 — First seam + one registry (ADR-008/009)** | **Partially specified** | Runtime-selection target is clear (`nexus_orchestration` selection exists; INV-37). But the *shadow/flag mechanism* is undefined (Condition 2), and how shadow decisions record as events (INV-39) is unspecified. ADR-009's "v1 runner as legacy adapter" shim is named, not designed. |
| **4 — Promote prototypes** | **Mostly specified** | `repo_profile`, `human_approval`, `git_actions` exist and are unit-tested. Gap: their **output contracts are unfrozen** (`repository_understanding`, `interaction`, `environment`), so "promotion" hardens demo-grade shapes into packages without a frozen target (Condition 5). Prototypable now; finishable after ADR-010. |
| **5 — Reasoning heads (Intent, Engineering)** | **Partially specified** | Intent Resolution: `goal.md`+`intent.md` frozen; reasoning-capability choice open (engineering G4). EI: the `engineering/` corpus is deep, but (a) no frozen `engineering_strategy` contract (G1), (b) **Estimation facet unspecified** (Condition 3). EI *core* (classification/approach) is buildable; EI *complete* is blocked. |
| **6 — First end-to-end workflow (flagged)** | **Partially specified** | Depends on Stages 1–5 conditions. Once they hold, wiring is specified (the A0/A1 verticals demonstrate the path). Blocked transitively, not intrinsically. |
| **7 — Operations/Estimation** | **Ambiguous** | No Operations design doc, no Estimation model. **Architecture incomplete** — cannot start without inventing both. |
| **8 — Strangle & retire duplicates** | **Mostly specified** | Removal order is clear (§9 of Blueprint); each removal gated on its owner carrying traffic. Low ambiguity, but depends on all prior stages. |

**Executability summary:** 1 fully, 4 mostly, 3 partially, 2 ambiguous. The ambiguity concentrates at the
**very first substrate stage** and the **last operations stage** — the two ends — plus the cross-cutting
flag mechanism. The middle (Policy, prototype promotion, EI-core) is executable.

---

## 2. Hidden Architectural Decisions (where a team would still invent architecture)

Each is a concrete, sourced gap — not a vague concern.

| # | Hidden decision | Evidence / source | Type |
|---|---|---|---|
| H1 | **Sync vs async persistence boundary** | `nexus_core/persistence/interfaces.py` all `def` (sync); `nexus/memory/manager.py` `async def`/`AsyncSession` | Undefined boundary |
| H2 | **Authoritative store model:** v1 CRUD vs v2 event-sourced | v1 SQLAlchemy models are mutable/authoritative; INV-13/14 require event-log authority; Blueprint binds them without resolving | Missing state model / undefined ownership |
| H3 | **Feature-flag + shadow-mode mechanism** | Blueprint Stages 3–8 depend on it; no flag system in repo; no spec for shadow-decision recording (INV-39) | Missing subsystem/protocol |
| H4 | **Estimation model** (complexity/duration/cost) | No `contracts/estimation*`; no design doc; EI + Operations depend on it | Missing contract + object ownership |
| H5 | **Operations metrics model** | No Operations doc in `docs/v2/`; no metrics contract | Undefined lifecycle/ownership |
| H6 | **Engineering Strategy contract** | `contracts/` has no `engineering_strategy.md`; engineering G1 defers it | Missing contract |
| H7 | **Repository Understanding contract + full subsystem** | no `repository_understanding.md`; indexing/cache/incremental/monorepo deferred (engineering G2) | Missing contract + undefined lifecycle |
| H8 | **Interaction contract + approver-identity model** | no `interaction.md`; identity "referenced not designed" (HI G-1) | Missing contract + missing ownership |
| H9 | **Environment/Session/Workspace contracts + Session↔Runtime-Session handshake** | no `environment.md`; actuation G-2 flagged *high*, "prose only" | Missing contract + undefined boundary |
| H10 | **Runtime-registry unification shim** (v1 runner → v2 adapter) | ADR-009 names it; no adapter-shim design | Undefined boundary |
| H11 | **Communication vs Channel-Harness vs Human-Interaction ownership in code** | Constitution ruled it; no contract binds the three names | Undefined ownership (low — ruling exists) |

H1–H5 are the **blocking** hidden decisions (they gate Stages 1/3/5/7). H6–H9 are **contract-freeze**
decisions (INV-07) that gate *finishing* the frontier subsystems but not *starting* their prototypes.
H10–H11 are low-severity, already-ruled, needing only a shim spec.

---

## 3. Migration Risks (per stage)

| Stage | Technical risk | Architectural risk | Operational risk | Rollback | Validation |
|---|---|---|---|---|---|
| 0 | none | none | none | revert docs | peer review |
| **1** | sync/async bridge deadlocks; data migration | **INV-13/14 violation if v1 store made authoritative** (H2) | corrupt shared state affects v1 | keep v1 store primary; v2 read-only shadow first | replay-equivalence test (INV-14); dual-read diff |
| 2 | policy eval perf | attribute vocabulary drift vs Estimation (H4) | fail-open regression | keep v1 policy path; flag off | differential test vs v1 outcomes; fail-closed test (INV-30) |
| **3** | flag plumbing (H3) | shadow decisions not recorded as events (INV-39); **dual registries violate INV-36 during coexistence** | wrong runtime chosen | flag off = byte-identical v1 | shadow-divergence log; canary slice |
| 4 | prototype hardening | **unfrozen output contracts** (H6–H9) hardened prematurely | none (flagged off) | packages unwired | unit tests; contract-shape review |
| 5 | LLM bounding (G4) | **no engineering_strategy contract; Estimation void** (H4/H6) | bad strategy → bad plan | flag off; EI emits to log only | determinism-seam replay (INV-17) |
| 6 | real-runtime cost/rate limit | transitive from 1–5 | user-visible if flag mis-set | per-flag rollback | shadow→canary→default gates |
| **7** | metrics accuracy | **Operations/Estimation undesigned** (H4/H5) | misleading dashboards | keep v1 metrics | reconcile vs event log |
| 8 | delete-before-converge | premature removal → outage | loss of v1 fallback | re-enable v1 path | traffic-moved gate before delete |

**Cross-stage architectural risks the Blueprint under-weights:** (a) INV-13 tension at Stage 1 (H2);
(b) temporary **INV-36 violation** (two runtime registries) across Stages 3–8; (c) temporary **INV-07
tension** (two policy/approval/persistence representations) during coexistence. All three are *temporary and
bounded* but the Blueprint should name them as accepted, time-boxed invariant exceptions (see §7).

---

## 4. ADR Readiness

| ADR | Enough to implement safely? | What's missing |
|---|---|---|
| **ADR-005** (reinstate EI; retire "Executive Intelligence") | **Mostly** | Cannot fully define EI's output because the **Estimation facet is unspecified** (H4) and `engineering_strategy` is unfrozen (H6). Sufficient to *start* EI-core; insufficient to *complete* EI. |
| **ADR-006** (name Policy/Repo/HI/Actuation/Operations packages) | **Yes** | A naming/authorization ADR; complete as scoped. |
| **ADR-007** (durable persistence) | **No — the critical gap** | Does not resolve **sync/async** (H1) or **event-sourced-vs-CRUD authority** (H2). As written it would let a team bind an authoritative mutable store under an event-sourced platform and silently break INV-13. Must specify: which store is authoritative, the sync boundary, and the event-log reconciliation. |
| **ADR-008** (strangler seam) | **No** | Omits the **flag/shadow infrastructure** (H3): where flags live, how shadow decisions are recorded as correlated events (INV-39), per-decision rollback semantics. Without these the "strategy" is a narrative, not an implementable contract. |
| **ADR-009** (one runtime registry) | **Mostly** | Needs the **v1-runner-as-legacy-adapter shim** design (H10) and the cutover point where INV-36 stops being temporarily violated. |
| **ADR-010** (freeze frontier contracts) | **Deferred by design** | Correct to defer, but Stages 4–5 cannot *finish* until `engineering_strategy`, `repository_understanding`, `interaction`, `environment` are frozen (H6–H9). |

**The two ADRs that block safe start are ADR-007 and ADR-008.** Both are described in the Blueprint as if
settled; both hide a load-bearing decision. These are the highest-priority pre-implementation artifacts.

---

## 5. Implementation Readiness Matrix

| Subsystem | Verdict | Evidence |
|---|---|---|
| **Policy Engine** | **Ready to implement** | Full frozen `contracts/policy.md` + `20_POLICY_ENGINE.md` + deterministic algorithm. (Corrects the Blueprint's "void" claim.) Minor: `cost_estimate` attribute waits on Estimation. |
| **Durable Memory integration** | **Needs clarification** | Protocols exist (`persistence/interfaces.py`) but **sync**; v1 store **async** + CRUD-authoritative vs INV-13/14 (H1/H2). ADR-007 must resolve before Stage 1. |
| **Intent Resolution** | **Needs clarification** | `goal.md`+`intent.md` frozen (seam ready); reasoning-capability choice open (G4). Core buildable; internals need the LLM-bounding decision. |
| **Engineering Intelligence** | **Needs clarification** | `engineering/` corpus deep; but no `engineering_strategy` contract (H6) and **Estimation void** (H4). Core (classify/approach) ready; complete blocked. |
| **Repository Intelligence** | **Needs clarification / Architecture incomplete (full subsystem)** | `repo_profile` prototype + `10_REPOSITORY_INTELLIGENCE` seam ready to promote; but indexing/cache/incremental/monorepo undesigned (G2) and no `repository_understanding` contract (H7). Prototype promotable; full subsystem incomplete. |
| **Human Interaction** | **Needs clarification** | `human_interaction/` corpus deep + `human_approval` prototype; but no `interaction` contract and **approver-identity model undesigned** (H8, G-1). Core approval loop ready; identity/RBAC incomplete. |
| **Operations** | **Architecture incomplete** | No design doc, no metrics model, depends on Estimation void (H5/H4). Cannot start Stage 7 without a design artifact. |

Ready: 1. Needs clarification: 4. Architecture incomplete: 1 (Operations) + 1 partial (Repository full
subsystem). This is the honest distribution: a strong majority is startable; a clear minority is blocked.

---

## 6. Contract Readiness

**Can every future subsystem be built on the current frozen contracts? No — five subsystems need a future
contract freeze (do not change existing contracts; freeze new ones via ADR-010).**

| Subsystem | Contract present? | Action needed |
|---|---|---|
| Policy Engine | ✅ `policy.md` | none — build now |
| Intent Resolution | ✅ `goal.md`, `intent.md` | none for the seam |
| Learn / Knowledge | ✅ `knowledge.md` | Constitution's "graph" upgrade is additive-later |
| Skills | ✅ `skill.md` | Constitution recommends adding `success_criteria`/tool/cost/approval expectations — **a future object version (ADR), not a change now** |
| Planning/Execution | ✅ `plan`,`work_package`,`execution_graph`,`execution_strategy` | none |
| **Engineering Intelligence** | ❌ no `engineering_strategy.md` | **freeze before Stage 5 completes** (ADR-010) |
| **Repository Intelligence** | ❌ no `repository_understanding.md` | **freeze before Stage 4 completes** |
| **Human Interaction** | ❌ no `interaction.md` | **freeze before Stage 4 completes** |
| **Actuation** | ❌ no `environment/session/workspace/permission.md` | **freeze before Stage 4 completes** |
| **Estimation** | ❌ none | **design + freeze before Stage 5/7** |
| **Operations** | ❌ none | **design before Stage 7** |

Existing contracts are **not** to be modified; the gap is *additional* frozen contracts, on the schedule
above. The Skill-completion the Constitution recommends is correctly a *new object version*, not an
in-place edit (the contract's §8 versioning rules permit exactly this).

---

## 7. Invariant Validation (does any stage temporarily violate an invariant?)

The 39 invariants are the safety floor. Most stages preserve them. **Three stages carry temporary,
bounded invariant tension the Blueprint should explicitly declare as accepted, time-boxed exceptions:**

| Invariant | Stage | Tension | Containment |
|---|---|---|---|
| **INV-13 / INV-14** (event log is truth; state is projection) | **1** | If v1's mutable CRUD store is made authoritative under v2, the event log is no longer the single source of truth. **Real risk, not hypothetical** (H2). | ADR-007 must keep the event log authoritative and treat the v1 store as a projection/read-model, or the stage is non-compliant. **This is a blocker, not a bounded exception.** |
| **INV-36** (one source of truth for provider availability) | **3–8** | Two runtime registries coexist during the strangle. | Bounded, acknowledged; ADR-009 must set the cutover date when it ends. Acceptable *temporary* exception. |
| **INV-07** (one canonical schema per object) | **2–8** | Dual policy/approval/persistence representations during coexistence. | Bounded; converge-then-delete (Blueprint §9). Acceptable *temporary* exception if declared. |
| **INV-39** (cross-subsystem interaction is a correlated event) | **3** | Shadow-mode decisions must be recorded as events; unspecified (H3). | ADR-008 must specify shadow-decision events. Blocker until specified. |
| **INV-30** (fail closed) | **2** | Policy extraction risks fail-open regression. | Differential + fail-closed tests; contained. |

**Verdict on invariants:** the Blueprint does **not** knowingly violate any invariant, but **Stage 1
(INV-13) and Stage 3 (INV-39) can violate one if implemented as literally written**, because the
resolving decision is absent. These are the same H1/H2/H3 gaps surfaced from the invariant angle — which
is corroborating, not new. INV-36/07 tensions are acceptable if *declared and time-boxed*.

---

## 8. Implementation Sequencing Review

**The proposed order is largely correct, with one strong-evidence change.**

The Blueprint puts **durable substrate (Stage 1) first** as "lowest-cost, highest-leverage." The evidence
says Stage 1 is instead the **most architecturally ambiguous** stage (H1/H2; INV-13 risk). Leading with the
riskiest, least-specified step contradicts "minimize migration risk."

**Recommended adjustment (evidence-based):**
- **Promote Stage 0 to include ADR-007 *and* ADR-008 resolution** (the sync/async + authority decision, and
  the flag/shadow spec) *before* any wiring. These are ~2 documents; they convert the two ambiguous stages
  into specified ones.
- **Start Stage 2 (Policy Engine) in parallel with Stage 0** — it is the single *ready* new subsystem
  (full contract + doc), needs no unresolved decision, and delivers the invariant-mandated governance core
  everything else depends on. Doing Policy first also de-risks Stage 3's approval seam.
- **Keep Stage 1 after its ADR-007 is resolved**, and begin it in **shadow/read-only** mode (v2 reads the
  v1 store; v1 stays authoritative) so INV-13 is never at risk during coexistence.
- Everything else (3→8) keeps the Blueprint order.

Net: **Policy Engine and the two blocking ADRs move to the front; the ambiguous substrate wiring moves
behind its own decision.** This strictly reduces risk and is justified by H1/H2 and the INV-13 finding —
meeting the "only change sequence with strong evidence" bar.

---

## 9. Remaining Ambiguities (the exact sources)

Consolidated, each pointing to its source so the team knows precisely what to resolve and where:

1. **Sync/async persistence boundary** — `nexus_core/persistence/interfaces.py` (sync) vs
   `nexus/memory/manager.py` (async). *Resolve in ADR-007.*
2. **Authoritative-store model** — v1 CRUD vs INV-13/14 event-sourcing. *Resolve in ADR-007.*
3. **Flag + shadow-mode mechanism, incl. shadow-decision events (INV-39)** — absent from repo and from
   Blueprint §8. *Resolve in ADR-008.*
4. **Estimation model** — no contract/doc; blocks EI-complete + Operations. *New design artifact.*
5. **Operations plane** — no `docs/v2/` doc. *New design artifact.*
6. **Frontier output contracts** — `engineering_strategy`, `repository_understanding`, `interaction`,
   `environment`/`session` unfrozen. *Freeze via ADR-010 on the §6 schedule.*
7. **Approver identity / RBAC** — HI G-1, "referenced not designed." *Fold into Policy/HI design.*
8. **v1-runner→v2-adapter shim** — ADR-009 names, doesn't design. *Add shim spec to ADR-009.*
9. **Session↔Runtime-Session handshake** — actuation G-2 (high), prose-only. *Freeze in `environment` contracts.*

Nothing here is a *redesign*; each is a bounded, nameable decision. That is the difference between
APPROVED WITH CONDITIONS and NOT READY.

---

## 10. Final Verdict

**Question:** *If five senior engineers started tomorrow, could they implement Nexus for the next year
without needing another foundational architecture document?*

**Verdict: APPROVED WITH CONDITIONS.**

**Evidence for approval:** the constitutional spine is built and tested; the Policy Engine — the invariant-
mandated governance core — is fully contracted and ready (correcting the Blueprint's own understatement);
the core object contracts are frozen and sufficient; the Strangler strategy is sound; and the majority of
Stages (0, 2, 4-prototype, 5-core) can begin immediately against stable architecture. A team would be
productively occupied for most of the year without touching the gaps.

**Evidence for the conditions (why not unconditional APPROVED):** the team would, within the first weeks,
hit four decisions that are *architecture, not implementation* — the sync/async + event-authority
persistence model (H1/H2, with a real INV-13 risk), the flag/shadow mechanism (H3, with an INV-39 gap),
the Estimation model (H4), and the Operations design (H5) — plus four unfrozen frontier contracts
(H6–H9). Strictly, they *cannot* go the full year without producing **~3–4 additional small foundational
artifacts**: a corrected **ADR-007** (persistence integration), a completed **ADR-008** (flag/shadow),
an **Estimation model**, and an **Operations design doc**. These are bounded and nameable — this review
names all of them — but they are foundational, so the honest answer to "no *new* foundational document"
is *no*.

**Why not NOT READY:** none of the gaps reopens the Constitution, contradicts an invariant by design, or
requires re-architecture. Every gap is a specific, downstream, resolvable artifact whose location is
pinned in §9. The foundation is sound; the frontier is unfinished at four known points.

**The conditions, precisely:**
- **C1 (blocking Stage 1):** Rewrite ADR-007 to resolve sync/async and keep the event log authoritative
  (INV-13); begin Stage 1 in read-only shadow.
- **C2 (blocking Stage 3):** Complete ADR-008 with the flag/shadow-event mechanism (INV-39) and per-
  decision rollback.
- **C3 (blocking Stage 5-complete):** Produce an Estimation model and freeze `engineering_strategy`.
- **C4 (blocking Stage 7):** Produce an Operations design doc + metrics model.
- **C5 (blocking Stage 4-complete):** Freeze `repository_understanding`, `interaction`, `environment`
  contracts (ADR-010) before hardening the promoted prototypes.
- **C6 (sequencing):** Move Policy Engine and the ADR-007/008 resolutions to the front (§8).

Meet C1–C6 — four small documents and two ADR rewrites, none a redesign — and the Blueprint becomes fully
executable end to end. Until then, the team should start on the ready majority (Policy, spine reshaping,
prototype promotion, EI-core) while the six conditions are closed in parallel.

**One-line verdict.** *APPROVED WITH CONDITIONS: the architecture is sound and two-thirds of the year is
executable today, but the durable-substrate authority model, the flag/shadow mechanism, the Estimation
model, the Operations plane, and four frontier contracts must be specified before their stages — six
bounded, named conditions, not a redesign — so five engineers can start tomorrow but not finish the year
without producing them.*

---

*This is a readiness review. It changes no invariant, contract, ADR, architecture, or roadmap (its one
sequencing recommendation is evidence-backed per the rules). It corrects prior Nexus documents only where
source evidence contradicted them, most notably restoring the Policy Engine from "void" to "ready." Every
ambiguity is pinned to its source so it can be closed without re-opening the Constitution.*
