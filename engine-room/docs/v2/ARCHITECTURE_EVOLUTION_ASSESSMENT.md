# Nexus — Architecture Evolution Assessment

Status: **Principal-architect strategic assessment.** Not a code audit, not an implementation review.
This document answers one question: *is the architecture required to realize the original Nexus vision
now sufficiently understood, or is architectural work still missing before implementation begins?*

Scope of evidence: `00_VISION.md`, `01_ARCHITECTURE.md`, `99_ARCHITECTURAL_INVARIANTS.md`, the numbered
`02–26` design docs, `VISION_ALIGNMENT_AUDIT.md`, `A0/A1/A2_IMPLEMENTATION_REPORT.md`, and the four
frontier design corpora `engineering/`, `actuation/`, `human_interaction/`, plus `knowledge/` and
`runtime/`. Read as *design*, not code. Prior "ratify and freeze" certifications inside each corpus
were treated as claims to test, not facts.

Rules honored: no implementation, no code, no ADR/contract/invariant/architecture modifications. This
is an assessment. It recommends evolution; it changes nothing. It prefers simpler architectures and
distinguishes **reasoning / governance / execution / operations** as separate concerns throughout.

---

## Executive Summary

**The headline.** Nexus's architecture is, at the *subsystem* level, unusually well understood — more
so than almost any pre-implementation system I have assessed. Engineering Intelligence, Actuation,
Human Interaction, Knowledge, and Runtime each have deep, internally consistent, self-audited design
corpora with named, bounded, non-blocking gaps. That is real architectural maturity and it should be
credited plainly.

**But there is no single architecture.** There are at least **three mutually contradictory top-level
models coexisting in the repository**, and roughly **five independent design corpora that never
reconcile into one canonical whole**:

1. **The numbered model** (`01_ARCHITECTURE.md`, marked "Phase 0 reconciled" per ADR-003): a 12-stage
   linear pipeline in which **Executive Intelligence is deprecated and folded into Intent Resolution**
   (Intent Resolution is given "classify work, identify complexity" as its own responsibilities).
2. **The engineering corpus** (`engineering/`): reinstates the strategy layer under a new name,
   **Engineering Intelligence**, inserted *between* Intent Resolution and Context Engineering, and
   deliberately **shrinks Intent Resolution back to pure `request→Goal` normalization** ("must not
   begin choosing skills or rigor"). It re-claims Work Classification for itself.
3. **The frontier subsystem corpora** (`actuation/`, `human_interaction/`, `knowledge/`, `runtime/`):
   cross-cutting subsystems that **do not fit the linear layer stack at all** — Actuation sits
   *beneath* the runtime-adapter boundary, not after Execution; Human Interaction declares itself "a
   cross-cutting shared subsystem, not a stage."

Each corpus cites the others by *seam* and each ends with "ratify and freeze the core." **Nobody has
drawn the map that contains all of them.** The strongest evidence that the real gaps are systemic, not
local: **three separate corpora — engineering, actuation, and human_interaction — independently name
the *same two* remaining frontiers** (a full Repository Intelligence subsystem, and the Human-
Interaction approval channel). When three teams working in isolation converge on the same two holes,
those holes are real — and the fact that each names them as "someone else's, deferred" is precisely the
symptom of a missing unifying owner.

**What surprised me (positive — architectural excellence to call out).**
- The **determinism seam** in `engineering/12_DECISION_FLOW.md` is genuinely elegant: heuristic (LLM)
  reasoning *before* strategy emission, immutable recorded decision *at* emission (INV-17),
  deterministic replay *after* — the same pattern the platform already trusts for runtime execution,
  applied one layer up. This resolves the "if EI uses an LLM the pipeline isn't deterministic" objection
  cleanly and is the right long-term answer to "where reasoning begins and determinism binds."
- The **approval ownership chain** (`human_interaction/05` + `actuation/07`): Planning identifies gates
  → Policy Engine decides requirement → Orchestration coordinates → Runtime/Actuation enforces the
  pause → Human Interaction surfaces → the approver decides. Every concern owned in exactly one place.
  This is textbook separation of governance from execution.
- The **decide/enforce/record discipline** in Actuation: Actuation acts and records but decides nothing;
  Recovery decides, Orchestration directs, Actuation enacts. Repeated verbatim across every chapter.

**Biggest missing architecture (genuine voids, not deferred seams).**
1. **The Policy Engine has no design corpus.** Three subsystems (EI, Actuation, HI) delegate the actual
   authorization decision to a "Policy Engine" (ADR-004, INV-28) that is *referenced everywhere and
   architected nowhere*. The governance plane's brain is an abstraction placeholder.
2. **Estimation is unmodeled.** Complexity, duration, and cost estimation — a named Executive-
   Intelligence responsibility in the original vision — appear in **no** corpus. The engineering corpus
   never mentions the concept; the numbered model asserts "identify complexity" with no design behind it.
3. **The Operations plane does not exist as architecture.** Cost, runtime utilization, tool usage,
   skill performance, success rate, recovery rate, bottlenecks — the vision's Layer 10 — have no design
   package anywhere (and, per the audit, no code).
4. **A durable operational-memory substrate is undefined.** Every frontier defers persistence; today
   everything is in-memory. "Learning" and "operational graph" cannot be real without it.

**Top three risks.**
1. **Architecture fork ossifying into implementation.** If teams begin building against whichever corpus
   they happen to read, the contradiction (Intent Resolution vs Engineering Intelligence owning
   classification; Communication vs Human Interaction owning channels) becomes two incompatible
   codebases. **Critical.**
2. **"Ratify and freeze" fatigue.** Five corpora each say "freeze the core." Freezing five cores that
   contradict each other freezes the contradiction. **High.**
3. **Governance depends on an unbuilt, undesigned brain.** Fail-closed is only as safe as the Policy
   Engine that decides "closed." Everything defers to it; it does not exist. **High.**

**Overall recommendation.** The layered pipeline was the right *starting* architecture and remains right
for the **reasoning spine**. It is the wrong shape for the *whole system*, which has visibly grown four
orthogonal concerns the frontier already discovered. **Do not freeze, and do not add more subsystems.
Do one architectural act first: unify.** Produce a single canonical model that (a) reconciles the EI/
Intent-Resolution fork, (b) places Actuation, Human Interaction, Repository Intelligence, and the Policy
Engine explicitly, (c) retires the linear-layer framing where subsystems are actually cross-cutting, and
(d) names the estimation, Policy Engine, durable-memory, and Operations voids as first-class subsystems
to design. My recommended target shape (Section: *Proposed Architecture vNext*) is a **five-plane
capability architecture** — a thin reasoning spine riding on four cross-cutting planes — because it is
simpler on the axis that matters (each plane has one verb: *reason / decide / act / ground / observe)
and it dissolves every misplacement this assessment identifies.

**Direct answer to the governing question.** *Sufficiently understood at the subsystem level; not yet at
the system level.* Meaningful architectural work remains before implementation — but it is
**reconciliation and re-shaping**, plus **four named voids**, not another round of subsystem invention.

---

## Layer-by-Layer Assessment

Rating = **architectural definition completeness** (complete / mostly complete / partially defined /
undefined), with the *why*. This is design maturity, not code.

| Layer | Rating | Why |
|---|---|---|
| **0 Foundation — Execution** | Complete | Generic provider-blind driver defined and built; boundary clean (`nexus_execution`). |
| **0 — Runtime Registry** | Complete | `runtime/04` + code; capability-typed, health-aware read lens. |
| **0 — Observability** | Mostly complete | Instrumentation sink defined; but "builds no dashboards, stores nothing durably" — no Operations consumer designed above it. |
| **0 — Persistence** | Partially defined | Protocols complete (`nexus_core/persistence`); **no durable backing designed for v2** (Alembic binds v1 only). Durable operational memory is undefined. |
| **0 — Governance / Policy Engine** | **Undefined (critical)** | Referenced by EI, Actuation, HI as the decider (ADR-004/INV-28); **no policy design corpus exists**. The most-depended-upon undesigned subsystem. |
| **0 — Approvals** | Mostly complete | Ownership chain excellently defined across `human_interaction/05` + `actuation/07`; depends on the undefined Policy Engine. |
| **0 — Communication** | **Contested** | Numbered `01` lists it as a cross-cutting service; `human_interaction/` proposes to absorb/supersede it as Channel Adapters but never reconciles the two. Ownership ambiguous. |
| **0 — Memory** | Partially defined | Generic in-memory store exists; durable *operational* memory (episodes, preferences) named and deferred by every corpus. |
| **0 — Scheduler / Outbox** | Undefined (v2 target) | Real in v1; absent from the v2 target model. Not modeled as v2 architecture. |
| **1 Harness — Runtime/Context/Validation/Knowledge/Recovery/Skill** | Mostly complete | Category model + resolvers defined and built; the strongest realized layer. |
| **1 — Channel Harness** | **Contested/undefined** | Not a `HarnessCategory` member; `human_interaction/10` claims Channel Adapters *are* Communication Harnesses. Same unreconciled overlap as Communication. |
| **2 Context Engineering** | Mostly complete | Eight context domains defined; deterministic assembly built. Gap: several *sources* (durable telemetry, Operator Profile, full Repository Intelligence) are not real subsystems yet; and EI now reads some of the same sources upstream (acceptable, but undeclared duplication). |
| **3 Skills** | **Partially defined** | `Skill` object exists but is **incomplete**: no `success_criteria` (lives on WorkPackage), no tool/cost/approval expectations, empty `procedure` everywhere. Selection defined; composition ownership resolved to EI. See *Skill Architecture* below. |
| **4 Executive / Engineering Intelligence** | **Mostly complete as a subsystem — but forked at system level** | `engineering/` is a strong, complete design (inputs, single output, determinism seam, governance posture). **But it contradicts the numbered `01` model**, and **estimation (complexity/duration/cost) is a void** in both. |
| **5 Orchestration Intelligence** | Partially defined | Sequencing/queue/approval-coordination/checkpoint defined. **delegate** and **merge** are undefined anywhere; **suspend/resume** ownership is split (Orchestration vs Supervision vs Actuation); **retry/escalate** collide with Recovery's ownership. |
| **6 Execution Intelligence / Supervision** | Partially defined / reshaped | `actuation/` redefines this space *beneath the adapter boundary* (Environments/Sessions/Workspaces/Permissions) — a strong design. But the numbered "Supervision" layer, the Execution FSM, Actuation, and Recovery now overlap on observe/validate/recover, cleanly on paper, unreconciled as one model. |
| **7 Reflection** | Mostly complete | Deterministic aggregation defined. Design limit: patterns require ≥2 episodes and no cross-run episode persistence exists → single-task path learns nothing. |
| **8 Knowledge** | Partially defined | Engine/acceptance/lifecycle well defined. But **"operational graph" is claimed and not modeled** (typed edges never traversed), durability undefined, and Knowledge **conflates four distinct grounding subsystems** (Repository/Operator/Execution/Skill Intelligence) that have different lifecycles. Category error to resolve. |
| **9 Planning** | Mostly complete | decompose→packages→dependencies→graph defined and built. Intelligent decomposition deferred (identity strategy); EI now supplies the envelope Planning works inside. |
| **10 Operations** | **Undefined** | Cost, utilization, tool usage, skill performance, success/recovery rate, bottlenecks — **no design package anywhere**. The vision's operational-intelligence layer is architecturally absent. |

**Verdict pattern:** the *lower-left* (execution substrate, harness, runtime) is complete; the
*reasoning spine* (EI→Context→Planning) is mostly complete but forked; and the *cross-cutting brains*
(Policy Engine, Operations, durable Memory, estimation) are undefined. Definition thins exactly where the
vision's differentiator lives.

---

## Responsibility Ownership Matrix

For each contested decision: who the three models say owns it, whether it is duplicated/misplaced, and my
single-owner verdict. **Nothing should decide in more than one place** (Rule 10 / INV-02).

| Decision | Original vision | Numbered `01` | Frontier corpora | Duplicated / misplaced? | **Single-owner verdict** |
|---|---|---|---|---|---|
| Understand intent → Goal | Exec. Intelligence | Intent Resolution | Intent Resolution | No | **Intent Resolution** |
| Classify engineering work (bug/feature/refactor…) | Exec. Intelligence | **Intent Resolution** | **Engineering Intelligence** | **YES — direct collision** | **Engineering Intelligence** (it is a *how* judgment; Intent Resolution should detect only domain, not engineering kind) |
| Estimate complexity | Exec. Intelligence | Intent Resolution ("identify complexity") | **unmodeled** | Void | **Engineering Intelligence** — *must be designed* |
| Estimate duration / cost | Exec. Intelligence | nobody | **unmodeled** | Void | **New: Estimation/Cost Intelligence** feeding EI — *genuine gap* |
| Choose engineering approach / strategy | Exec. Intelligence | Execution Strategy layer | EI proposes Coordination Intent → Execution Strategy formalizes | Seam (settled) | **EI proposes; Execution Strategy formalizes** |
| Choose skills | Exec. Intelligence | Skill Selection | EI declares requirements; Skill Selection resolves | No | **Skill Selection resolves** |
| Choose runtime | (execution) | Orchestration | Orchestration selects; EI expresses posture | No | **Orchestration selects** (INV-37) |
| Decide approval *required* | Exec. Intelligence | Orchestration/Governance | **Policy Engine** decides; EI proposes gate; Planning identifies | No (well-chained) | **Policy Engine** (once it exists) |
| Decide approval *outcome* | (human) | — | the approver via Human Interaction | No | **The approver** (HI surfaces, never decides) |
| Retry | Orchestration | **Orchestration + Execution Strategy** | **Recovery decides**; Orchestration directs | **YES — three claimants** | **Recovery decides; Orchestration directs; Actuation enacts** |
| Escalate | Orchestration | Orchestration/Supervision | Recovery decides | **YES — split** | **Recovery decides** |
| Suspend / resume | Orchestration | Orchestration + Supervision | Actuation enacts; Recovery/Orchestration direct | **YES — split across 3** | **Recovery/Orchestration direct; Actuation enacts** |
| Delegate / merge | Orchestration | Orchestration (named) | **undefined anywhere** | Void | **Orchestration** — *must be designed* |
| Observe → Observation | Supervision | Supervision | Actuation emits facts; Supervision derives | No (clean) | **Supervision** (Actuation only emits) |
| Validate → Evidence | Validation | Validation | Actuation emits candidates; Validation promotes | No (clean) | **Validation** |
| Persist Knowledge | Knowledge | Knowledge | Reflection proposes; Knowledge Acceptance decides | No | **Knowledge Acceptance Engine** |
| Human-approval *channel* | (unowned) | Communication? | **Human Interaction** | Contested vs Communication/Channel Harness | **Human Interaction** (once reconciled) |
| Repository understanding | (implicit) | Context Engineering | **Repository Intelligence** (separate) + consumed by EI & Context | Dual-consumer (fine) | **Repository Intelligence** (separate subsystem) |

**Reading:** the *settled* rows are where a frontier corpus has already done reconciliation work
(approvals, skills, runtime, observe/validate). The *collision/void* rows (classification, estimation,
retry/escalate/suspend, delegate/merge, channel ownership, Policy Engine) are exactly the unreconciled
seams and the genuine gaps.

---

## Dependency Diagram (verified, with hidden coupling and cycle checks)

The declared law is one-way, downward (`01` Dependency Direction; INV-01). Verified against the corpora:

```
                 Intent Resolution
                        │  Goal ▼
     ┌──────────── Engineering Intelligence ───────────┐   reads (read-only, by value):
     │  emits Engineering Strategy (immutable, INV-17) │     • Repository Understanding (Repo Intel)
     │                                                 │     • Knowledge (read-only query)
     ├─► Context Engineering                           │     • Operator Preferences (Operator Profile)
     ├─► Planning                                      │     • Policy Context (Policy Engine)
     ├─► Execution Strategy                            │     • Environment Facts (Harness Registry)
     ├─► Skill Selection                               │
     ├─► Orchestration ──► Runtime Manager ──► Execution Engine ─┐
     └─► Validation                                             │ (adapter boundary)
                                                                ▼
                                                          [ Actuation ]  operates External Environment
                                                                │ actuation.* facts
                                          Supervision ◄─────────┘  ► Observations
                                          Validation  ◄──────────  ► Evidence
                                          Recovery    ◄──────────  ► decides; Orchestration directs

  cross-cutting (touch every layer via events / read-only seams, own no pipeline stage):
     Policy Engine · Human Interaction · Knowledge · Observability/Operations · Memory · Repository Intelligence
```

**Dependency verdicts.**
- **EI → {core, infra} only** (`engineering/00`): correct and enforced. EI imports no downstream engine;
  downstream engines cannot reach up. This is the right shape and should be the template for every
  reasoning subsystem.
- **Actuation → {core, infra} only, consumed behind the adapter boundary** (`actuation/00`): correct;
  Actuation cannot reach the Goal (INV-22 made physically unbreakable — it only ever receives a Work
  Package). Excellent.
- **Human Interaction coupled only through events** (`human_interaction/00`): correct as a cross-cutting
  peer — but its relationship to the Layer-0 **Communication** service and Layer-1 **Channel Harness** is
  a **latent naming cycle of ownership**: three names (`Communication` service, `Channel Harness`
  category, `Channel Adapter = a Communication Harness`) for one concern, unreconciled.

**Hidden coupling to flag.**
1. **The Policy Engine is a universal upstream dependency with no node.** EI, Actuation, HI, Orchestration
   all depend on "Policy decides." An undesigned subsystem sitting on everyone's critical path is the most
   dangerous hidden coupling in the architecture.
2. **Actuation-Session ↔ Runtime-Session handshake** (`actuation/13` G-2, self-rated *high*): "the load-
   bearing new relationship," specified in prose, not contract. Ownership of a long-lived Session that
   outlives one runtime attempt could blur in implementation.
3. **Estimation feeds EI's coherence rules but has no producer.** EI's autonomy≤f(risk) and rigor≥g(risk)
   presume risk/complexity are known; nothing computes them.

**Cycle check.** No true import cycles in the design (dependency law holds). The only "cycle" is
*informational and intended*: Reflection → Knowledge → (future) Planning/EI grounding — a learning loop
across time, not a call cycle. That is correct.

**Scalability concerns.** (a) All state in-memory → no horizontal scale, no restart durability (every
corpus defers). (b) Environment/Session concurrency and back-pressure "flagged not designed"
(`actuation/13` G-4, `runtime/20` G-3) — capacity is unmodeled. (c) Multi-node/distributed actuation
undefined (`actuation/13` G-10). (d) Multi-goal/portfolio strategy undefined (`engineering/14` G-8).
These are all *Stage-3/4* concerns and correctly deferred — but they must be *named in the unified model*
so they aren't rediscovered late.

---

## Information Flow (not execution — information)

```
Operator request
     │
     ▼
Intent Resolution ──────────────► Goal (frozen contract)
     │
     ▼
Engineering Intelligence  ◄── reads ── Repository Understanding, Knowledge, Operator Preferences,
     │                                 Policy Context, Environment Facts
     ▼
Engineering Strategy (immutable decision event)
     │  parameterizes ▼
Context Engineering ──► Context Package ──► Planning ──► Plan + Work Packages + Execution Graph
     │                                                        │
     ▼                                                        ▼
(Skill Selection resolves capabilities)              Orchestration ──► Runtime ──► Execution ──► Actuation
                                                                                         │ facts ▼
                                                          Supervision ──► Observations ──┤
                                                          Validation ──► Evidence ───────┤
                                                          Reflection ──► Patterns ───────┘
                                                                 │
                                                                 ▼
                                                    Knowledge (accept/evolve) ──► future EI + Planning grounding
```

**Context audit — is every required dimension sourced?** The vision names 8 context domains
(Goal/Domain/Workspace/Historical/Operational/Constraint/Resource/Execution). Mapping to real sources:

| Context dimension | Source subsystem | Status |
|---|---|---|
| Goal | Intent Resolution | Defined |
| Domain | Intent Resolution | Defined |
| Workspace | Actuation (Workspace/Environment) | Designed, not built |
| Historical (prior executions/failures/recoveries) | Knowledge + Reflection + **Execution History** | **Execution History undefined as a subsystem** |
| Operational (telemetry, health, cost) | **Operations** | **Undefined** |
| Constraint | Policy Engine + Goal constraints | **Policy Engine undefined** |
| Resource (runtime capability, env facts) | Harness Registry | Partial |
| Execution | Execution/Actuation events | Designed |
| Repository / Architecture | **Repository Intelligence** | Seam only; full subsystem undefined |
| Operator preferences | **Operator Profile** | Seam only; undefined |

**Missing information the flow needs and cannot yet get:** durable execution history, operational
telemetry/cost, full repository understanding, operator profile, and resolved policy context. Five of the
ten context dimensions depend on subsystems that are *named but undesigned*. **Context Engineering is
architecturally complete but source-starved.**

**One duplication to acknowledge (acceptable):** EI and Context Engineering both read Repository
Understanding and Knowledge. Different purposes (EI to *decide the approach*, CE to *assemble execution
context*), so this is legitimate dual-consumption — but the unified model should state it explicitly so
it isn't mistaken for a responsibility overlap.

---

## Decision Flow (decisions separated from execution)

The prompt's discipline — *every decision owned in exactly one place, reasoning separated from
governance from execution* — is best expressed by classifying each decision into one of four verbs:

| Verb | Meaning | Owners | Reasoning allowed? |
|---|---|---|---|
| **REASON** | judgment about *how* to proceed | Intent Resolution, **Engineering Intelligence**, Reflection | **Yes** — LLM/heuristic, bounded by the determinism seam (emit → record → replay) |
| **DECIDE (govern)** | authorize / permit / require-approval | **Policy Engine**, the approver (via Human Interaction) | **No** — deterministic policy evaluation, fail-closed (INV-28/30) |
| **DIRECT (coordinate)** | sequence / retry / escalate / suspend | Orchestration, **Recovery** | No — deterministic rules over recorded state |
| **ACT (enact)** | perform / enforce / record | Runtime, Execution, **Actuation** | No — holds no intelligence |

Placing the contested decisions:
- **Intent classification** → REASON, Engineering Intelligence (resolve the collision away from Intent
  Resolution). Intent Resolution reasons only about *what the operator wants*, not *what kind of
  engineering it is*.
- **Runtime selection** → DIRECT, Orchestration (EI only expresses REASONed posture). ✔ settled.
- **Skill selection** → DIRECT/resolve, Skill Selection (EI only REASONs requirements). ✔ settled.
- **Approval requirement** → DECIDE, Policy Engine. **Approval outcome** → DECIDE, the approver. ✔ well-
  designed, blocked only on the Policy Engine existing.
- **Execution strategy** → EI REASONs Coordination Intent; Execution Strategy layer deterministically
  formalizes. ✔ settled (seam G-7 to refine).
- **Retry / escalation / suspend-resume** → DIRECT, **Recovery decides + Orchestration directs +
  Actuation enacts**. Resolve the numbered model's placement of retries inside Orchestration *and*
  Execution Strategy — that is the one live triple-ownership defect.
- **Knowledge persistence** → the Knowledge Acceptance Engine DECIDEs (governed accept/evolve/merge/
  reject); Reflection only REASONs candidates. ✔ settled.
- **Human approval** → REASON where a gate is needed (EI), DECIDE the requirement (Policy), enact the
  pause (Runtime/Actuation), surface it (Human Interaction), DECIDE the outcome (approver). ✔ excellent
  chain.

**Where reasoning begins and determinism binds** (crediting `engineering/12`): reasoning is confined to
the REASON verb and *always* emits an immutable recorded decision; every other verb is deterministic and
replayable. **Where policy overrides reasoning:** always — the DECIDE verb is a hard ceiling; EI's
proposed autonomy/risk are inputs bounded by policy that fails closed. This four-verb split *is* the
"distinguish reasoning/governance/execution/operations" the assessment was asked to enforce, and it maps
almost perfectly onto the frontier designs — which is strong evidence the frontier is on the right track
and only needs unifying.

---

## Missing Architecture (foundational subsystems still absent)

Classified by whether the *architecture* (not code) exists.

| Subsystem | Architecture status | Severity | Note |
|---|---|---|---|
| **Policy Engine** | **Named, undesigned** | **Critical** | ADR-004/INV-28 make it the universal decider; no `policy/` corpus. Everything fails closed to a brain that doesn't exist. |
| **Estimation / Cost Intelligence** (complexity, duration, cost) | **Undefined (void)** | **High** | Named in vision as Exec-Intelligence duty; absent from every corpus. Blocks risk/autonomy calibration and Operations. |
| **Operations / Operational Intelligence** | **Undefined** | **High** | Cost, utilization, tool/skill performance, success/recovery rate, bottlenecks. The vision's Layer 10 has no design. |
| **Durable Operational Memory** (persistence substrate) | Deferred by all | **High** | No learning, no graph, no cross-run history without it. |
| **Human Interaction channel** | **Designed, unbuilt, unreconciled** | High | Strong corpus; blocked as "someone else's"; overlaps Communication/Channel Harness unresolved. |
| **Repository Intelligence (full subsystem)** | Seam fixed; subsystem deferred (`engineering/14` G2) | High | Grounding for EI and Context; A2 built a demo profile, not the subsystem. |
| **Operator Profile / Operator Intelligence** | Seam named (`engineering/02`) | Medium | EI personalization + Context source; representation undesigned (G3/G9). |
| **Execution History** | Implicit in Knowledge | Medium | Distinct lifecycle from Knowledge; should be its own queryable store. |
| **Capability / Environment Discovery** | Partial (Harness Registry) | Medium | Health/capability facts partially modeled; discovery/refresh undefined. |
| **Tool Intelligence** | Undefined | Medium | Which tools exist, their cost/risk, selection — unmodeled. |
| **Intent Resolution** (the reasoning stage) | Designed (`16`), scope forked | Medium | Exists; its *boundary* (does it classify work?) is the fork to resolve. |
| **Engineering Intelligence** | Designed (`engineering/`), fork | — | Complete as subsystem; reconcile with numbered `01`. |
| **Scheduler / Outbox (v2)** | Undefined in v2 target | Low | Real in v1; decide whether v2 re-owns or reuses. |

**Pattern:** the missing subsystems cluster in **governance (Policy Engine), operations (Operations,
Cost, Execution History), and grounding (Repository Intelligence, Operator Profile, Tool Intelligence)** —
i.e., the three cross-cutting planes, not the reasoning spine. This is the clearest signal that the
architecture should evolve from "layers" to "planes."

---

## Architectural Risks

| # | Risk | Likelihood | Impact | Rank |
|---|---|---|---|---|
| R1 | **The EI/Intent-Resolution fork is built twice** (classification owned in two models) → incompatible codebases | High | High | **Critical** |
| R2 | **Governance depends on an undesigned Policy Engine**; fail-closed is unverifiable | High | High | **Critical** |
| R3 | **Five "freeze the core" certifications freeze a contradiction** — no unified model to freeze | High | High | High |
| R4 | **Communication / Channel Harness / Human Interaction** triple-own the channel concern | Med | High | High |
| R5 | **Estimation void** → EI's risk/autonomy coherence rules run on unknowable inputs | Med | Med | Medium |
| R6 | **No durable memory** → "learning" and "operational graph" remain aspirational; Stage-3 unreachable | High | Med | High |
| R7 | **Actuation-Session ↔ Runtime-Session** ownership blurs (self-flagged G-2 high) | Med | Med | Medium |
| R8 | **Operations plane absent** → the platform cannot report cost/health/performance it promises | High | Med | Medium |
| R9 | **Retry/escalate/suspend triple-ownership** (Orchestration/Recovery/Supervision) | Med | Med | Medium |
| R10 | **Knowledge conflates four grounding subsystems** → one store with four incompatible lifecycles | Med | Med | Medium |

**The two Criticals share one root cause:** there is no single owner of the *whole* architecture, so
forks (R1) and unbuilt universal dependencies (R2) persist because each corpus correctly scopes them as
"out of my package."

---

## Recommended Evolution

Sequenced. Each step is architectural (design/reconciliation), not implementation.

**Phase A — Unify (before any further building).**
1. **Resolve the EI/Intent-Resolution fork.** Ratify one model: Intent Resolution = pure `request→Goal`
   normalization (detect *what/domain*); Engineering Intelligence = the strategy-cognition layer (decide
   *how*, including Work Classification). Update `01_ARCHITECTURE.md`'s "deprecated alias" note
   accordingly. (This is a reconciliation recommendation; execution of it is a Phase-0/ADR act, not part
   of this assessment.)
2. **Draw the single canonical map.** One document that places Intent Resolution, Engineering
   Intelligence, Context, Planning, Orchestration, Runtime, Execution, Actuation, Supervision,
   Validation, Recovery, Reflection, Knowledge **and** the cross-cutting subsystems (Policy Engine, Human
   Interaction, Repository Intelligence, Operator Profile, Operations, Memory) in one model. Adopt the
   plane framing (below) so cross-cutting subsystems stop being forced into the linear stack.
3. **Design the Policy Engine.** It is the load-bearing undesigned subsystem; nothing governed is safe
   until it exists as architecture.

**Phase B — Fill the named voids.**
4. Estimation/Cost Intelligence (feeds EI + Operations). 5. Operations plane (metrics/cost/history).
6. Durable operational-memory substrate (unblocks learning + graph). 7. Repository Intelligence as a full
   subsystem (`docs/v2/repository/`).

**Phase C — Reconcile the overlaps.**
8. Communication/Channel-Harness/Human-Interaction → one channel ownership. 9. Retry/escalate/suspend →
   one Recovery-decides model. 10. Knowledge → split grounding subsystems out of the learning graph.

**Phase D — Then build**, one vertical at a time (the A0/A1/A2 discipline was right), *against the unified
model*, and connect it to the running product (the `VISION_ALIGNMENT_AUDIT` integration gap).

**What to remove/merge (simpler is better).**
- **Merge** "Supervision" (numbered layer) into the Operations/observation plane — it is observation, not
  a pipeline stage.
- **Stop treating** Human Interaction, Policy Engine, Repository Intelligence, Operations as *layers* —
  they are cross-cutting planes; forcing them into the linear stack is what created the overlaps.
- **Collapse** "Execution Strategy," "Skill Selection," "Work Packaging" from three sequential *layers*
  into responsibilities of Planning parameterized by the Engineering Strategy — they are facets of "turn
  the decided approach into executable work," not independent stages. This removes three stage-boundaries
  that carry no independent decision.

---

## Proposed Architecture vNext

**A five-plane capability architecture: a thin reasoning spine riding on four cross-cutting planes.**
This is not a rewrite of the subsystems — every frontier design survives intact. It is a *reshaping of
the top-level model* so the subsystems compose without contradiction, and so each plane has exactly one
verb.

```
                        ┌───────────────────────────────────────────────┐
   REASONING SPINE ►    │ Intent Resolution → Engineering Intelligence   │  (REASON: emit recorded
   (sequential, thin)   │   → Planning (Context+Skills+Packaging+Strategy)│   decisions, INV-17)
                        └───────────────────────────────────────────────┘
                              ▲ grounds        │ parameterizes / directs
   ───────────────────────────┼───────────────┼───────────────────────────────────────────
   GROUNDING & LEARNING PLANE │               ▼                       EXECUTION PLANE
   (feeds the spine):         │        Orchestration → Runtime → Execution → Actuation   (ACT)
     Repository Intelligence  │                                    (environments/sessions/
     Operator Profile         │                                     workspaces/permissions)
     Knowledge (graph)  ◄─────┘                                             │ facts
     Execution History                                                      ▼
     Reflection ─────────────────────────────────────────────────► (Supervision derives Observations)
   ───────────────────────────────────────────────────────────────────────────────────────
   GOVERNANCE PLANE (DECIDE, fail-closed):  Policy Engine · Approvals chain · Human Interaction
   OPERATIONS PLANE (OBSERVE):  Observability · Supervision · Operations metrics · Cost/Estimation
   FOUNDATION (substrate):  Durable Memory/Persistence · Event Gateway · Harness Registry · Scheduler
```

**Why this is the right long-term shape (and simpler):**
- **One verb per plane** — Reason / Ground / Act / Decide / Observe — which is precisely the
  reasoning/execution/governance/operations separation the assessment was asked to enforce. Every
  misplacement in the Responsibility Matrix dissolves because the contested decision belongs to exactly
  one verb.
- **Cross-cutting subsystems stop being fake layers.** Policy Engine, Human Interaction, Repository
  Intelligence, Operations were never pipeline stages; the linear model forced them to be, creating the
  overlaps. As planes, they touch the spine through read-only seams and events (exactly as the frontier
  corpora already describe themselves).
- **The reasoning spine stays linear and short** — Intent → Strategy → Plan — which is where sequential
  layering genuinely fits, and where the determinism seam lives.
- **It survives five years** because runtimes/providers change inside the Execution plane without
  touching the spine; new grounding sources join the Grounding plane without new stages; and the
  governance plane can grow (RBAC, multi-operator, portfolio policy) without reshaping anything above it.

**Skill Architecture (the complete model this enables).** For Skills to be "engineering knowledge, not
prompts," the `Skill` contract should own **all** of: capability identity, `required_context`
(objectives), `execution_strategy` (procedure/approach), `validation_strategy`, `expected_artifacts`,
`recovery_strategy`, **`success_criteria`** (currently only on WorkPackage — pull it onto the Skill),
`tool_requirements`, `runtime_preferences` (capability posture, never a provider), `cost_expectations`,
and `approval_expectations` (default gate posture). Then EI declares *requirements*, Skill Selection
resolves to a *fully-specified* Skill, and Planning packages it — no facet is invented downstream. This
is the missing 5th field plus four expectations the vision implies but the current object omits.

**Knowledge Architecture (long-term).** Split the vision's "Knowledge includes Repository/Operator/
Execution/Skill Intelligence" — that is a category error. Recommended: **Knowledge = the operational
*learning graph*** (typed, actually-traversed edges over validated patterns, on a durable substrate);
and **Repository Intelligence, Operator Profile, Execution History, Skill Intelligence = separate
grounding subsystems** on the Grounding plane, each with its own lifecycle, each a *producer/consumer* of
Knowledge, not a part of it. Evolve Knowledge from today's flat dict toward a real graph *only when a
second consumer traverses an edge* — but design the durable substrate now, because every learning claim
depends on it.

**Five-year architecture (capabilities, not features).** To be the operating system for AI engineering,
the planes above must additionally acquire: (1) **multi-operator / multi-tenant governance** (identity,
RBAC, portfolio policy) in the Governance plane; (2) **multi-goal / portfolio reasoning** above EI
(sequencing, shared context, portfolio risk — `engineering/14` G8); (3) **distributed actuation** and
capacity/back-pressure (Execution plane — `actuation/13` G4/G10); (4) **a cost economy** (estimation →
budget → accounting → optimization) spanning Operations + Governance; (5) **durable, queryable
operational memory at scale** (the substrate under Grounding); and (6) a **capability marketplace** —
runtimes, skills, tools discovered and governed uniformly through the Harness Registry. None of these
requires abandoning the plane model; each lands in exactly one plane. That is the test of a five-year
architecture, and the plane model passes it where the linear stack does not.

---

## Final Verdict

**Is the architecture required to realize the vision now sufficiently understood?**

- **At the subsystem level: yes, and impressively so.** Engineering Intelligence, Actuation, Human
  Interaction, Knowledge, and Runtime are deeply, consistently, self-critically designed. The
  determinism seam, the approval chain, and the decide/enforce/record discipline are genuinely
  excellent and should be preserved verbatim. Very little *subsystem* architecture remains to invent.

- **At the system level: no.** There is no single canonical architecture — there are three contradictory
  top-level models and five unreconciled corpora, a load-bearing undesigned Policy Engine, unmodeled
  estimation and Operations planes, no durable memory, and a linear-layer framing that no longer fits the
  cross-cutting subsystems the platform has grown. The most telling evidence is convergent: three
  independent corpora name the same two frontiers and each hands them to "someone else."

**Should the current layered architecture evolve before further implementation?** **Yes — it should
evolve, not by adding subsystems, but by unifying them and re-shaping the top-level model.** The linear
layer stack is the right architecture for the *reasoning spine* and the wrong architecture for the
*whole system*. The recommended evolution is a **five-plane capability architecture** (reason / ground /
act / decide / observe) that keeps every good subsystem design, dissolves every responsibility collision
this assessment found, names every void, and still makes architectural sense in five years.

**One-line verdict.** *The parts are understood; the whole is not. Nexus does not need more architecture
— it needs its architecture unified into one model, its three cross-cutting voids (Policy Engine,
Estimation/Operations, durable Memory) designed, and its linear layers re-shaped into planes — before
the next line of implementation is written.*

---

*This is a strategic assessment. It modifies no ADR, contract, invariant, or existing architecture
document, and recommends no code. Its recommendations (reconcile the fork, design the Policy Engine,
adopt the plane model) are proposals for the architecture owner to ratify, not changes made here.*
