# Human Interaction — Architecture Review & Ratification

Status: Design review (design only). No implementation, no ADR/contract/invariant change.

This review evaluates the Human Interaction architecture (`README`, `00`–`13`) for correctness,
completeness, and readiness, answers the ratification questions, and states whether Human Interaction
completes Nexus' human-in-the-loop architecture or whether further foundational subsystems remain.

---

# 1. Dependency direction

**Verdict: sound and structurally enforced by pure event coupling.**

```
nexus_human_interaction → { nexus_core, nexus_infra }   (only)
        ▲
        │ consumed by provider-specific Channel Adapters (Communication Harnesses)
every subsystem ──interaction-request event──► Event Log ──► Human Interaction
Human Interaction ──response/decision event──► Event Log ──► requesting subsystem
```

- HI imports no engine; no engine imports HI. Both edges are event-mediated (INV-39), exactly the
  surface-agnostic model the approval callback already mandates (`../runtime/14` §5). This matches
  every layer built so far (`→ {nexus_core, nexus_infra}`).
- Provider knowledge lives only in Channel Adapters (`10`); the HI core is channel-agnostic.

---

# 2. Non-duplication of existing systems

**Verdict: the central risk, addressed — HI consolidates, it does not compete.**

- **Approvals:** HI *is* the canonical "surface" the approval model already delegates to
  (`../runtime/14` §4–5); it changes nothing in Planning's gate identification, Orchestration's
  coordination, the Policy Engine's evaluation, the approver's authority, or RM/Actuation's
  enforcement (`05`). It carries the single ADR-004 `ApprovalTaxonomy`; it invents none (INV-07).
- **Clarification:** Intent Resolution and EI still *decide* to ask and *interpret* answers (`../16`,
  `../engineering/`); HI carries the exchange (`04`).
- **Notifications:** channel-agnostic; providers are adapters (`06`/`10`) — not a Notification
  Service.
- **Operator Experience:** unchanged; it is the read-only *pull* surface, HI the interactive *push/
  request* surface (`06`). No overlap.

---

# 3. Boundary correctness

**Verdict: every seam is one-directional and decides nothing it should not.**

- Policy Engine evaluates; HI carries (INV-28). ✔
- The approver authorizes; HI records (INV-29). ✔
- Planning/Orchestration identify/coordinate gates; HI is the surface (`05`). ✔
- RM/Actuation enforce the pause; HI presents and collects (`../runtime/14`, `../actuation/07`). ✔
- Recovery decides a timeout's meaning; HI reports the timeout (`09`). ✔
- Knowledge is written only via Reflection; a Response is a recorded input, not a learned fact
  (INV-25/26, `07`). ✔

The load-bearing discipline (carry, never decide) is the human-facing form of RM's "pauses; does not
decide" (`../runtime/14` §1).

---

# 4. Object-model & type completeness

**Verdict: complete and closed.**

- Five objects (Interaction, Interaction Request, Interaction Session, Response, Decision) cover every
  touchpoint and wrap the existing approval contract rather than rivaling it (`02`).
- Eight interaction kinds are argued complete via the direction × reply-nature partition; rejection and
  decision are correctly modeled as *outcomes*, not kinds (`03`).
- Response schemas are a closed set of shapes with an extensible member list (`07`) — new needs extend
  schemas, never the kind list.

---

# 5. Determinism, governance, failure

**Verdict: strong.**

- A human response is captured once as a recorded event (INV-17); replay never re-asks — the same seam
  as recorded LLM output and the existing approval decision (`07`, `../runtime/14` §4).
- Every interaction is immutable, correlated, causation-linked (INV-13/31/39); "who authorized what,
  when, on which channel" is reconstructable (`08`, `11`).
- Fail-closed is absolute: no/ambiguous answer never becomes an implicit grant (INV-30); conflicts
  settle deterministically; duplicates dedupe idempotently (INV-16) (`09`).

---

# 6. Readiness & extensibility

**Verdict: ready to implement against fixed seams.**

Reuses the Phase-2 substrate and the existing approval/event model unchanged. New channels absorb as
adapters with no core change (`12`); the reference autonomous sequence (clarify → escalate → approve →
notify) is walked end-to-end (`12`). Every open item (`13`) is non-blocking; the one high-urgency gap
(approver identity, G-1) is a Governance/identity concern HI *consumes*, not owns.

---

# Ratification questions

### 1. Can Human Interaction be implemented without architectural ambiguity?
**Yes.** Subsystem, placement, object model, interaction kinds, conversations, approvals,
notifications, responses, events, failures, channel adapters, and governance are all specified
(`00`–`12`). Open items are deferred and non-blocking (`13`).

### 2. Does it preserve the existing approval model, ADR-004, and Orchestration's coordination?
**Yes.** It is the canonical surface that model already delegates to; it carries the single
`ApprovalTaxonomy` and invents no verdict or taxonomy (`05`, INV-07). Planning/Orchestration/Policy
Engine/RM/Actuation roles are unchanged (§2/§3).

### 3. Does it preserve the one-way dependency flow and provider independence?
**Yes — structurally.** Pure event coupling both ways (INV-39); provider knowledge only in Channel
Adapters (`10`, INV-32/34/36); no engine import either direction.

### 4. Does it preserve determinism, auditability, and fail-closed governance?
**Yes.** Responses recorded as data (INV-17); every interaction audited (INV-31/39); no answer never
implies consent (INV-30) (`09`/`11`).

### 5. Does it change any existing engine, contract, ADR, or invariant?
**No.** It adds a subsystem consumed only through events and by provider-specific Channel Adapters; it
modifies no engine, contract, ADR, or invariant. Previous programs remain green by construction.

---

# Does Human Interaction complete Nexus' human-in-the-loop architecture?

**Yes — it completes the human-in-the-loop *mechanism*, and it closes the specific loop every prior
review left open.** With HI defined, the platform finally has a canonical, governed, provider-
independent way to reach a human for any purpose: the approval gates Engineering Intelligence proposes
(`../engineering/08`) and Actuation enforces (`../actuation/07`) can now actually be *answered*; the
clarifications Intent Resolution and EI need can be *asked*; the escalations Recovery raises can reach
a person; and the reference request — *"fix the bug, validate, commit, report back"* — is completable
unattended except at the gates a human must clear (`12`).

Combined with the two prior design frontiers, the autonomous engineering spine is now architecturally
whole across **decision → performance → human authority**:

```
Engineering Intelligence (decide how, place gates)
   → Runtime (select/allocate) → Execution (drive) → Execution Actuation (operate + gate the real env)
   → Human Interaction (reach the human at every gate/clarification/escalation)
   → Validation (judge) → Recovery / Reflection / Knowledge
```

**Are additional *foundational* subsystems still required before Nexus can safely operate as an
autonomous engineering control plane? — No new *foundational* subsystem; the remaining work is
*grounding and identity*, not a missing pillar.**

Honestly stated, three things remain, none of which is a new architectural pillar:

1. **Approver identity & authorization (a Governance extension, not a new subsystem).** HI records
   *who answered*; *who may answer* is a Governance/identity model HI consumes (`13` G-1, INV-29). This
   is a defined extension of existing Governance, not a new foundation.
2. **Repository Intelligence as a full subsystem (grounding, not a pillar).** The decision/performance/
   human-authority spine is complete, but how *well* Nexus decides what to actuate is bounded by how
   well it understands the repository (`../engineering/10`, `../engineering/14` G2). The seam is fixed;
   the subsystem is deferred.
3. **The transition from design to implementation.** Engineering Intelligence, Execution Actuation, and
   Human Interaction are ratified *designs*. The remaining foundational work is not another
   architecture — it is *building* these three, wiring the real runtimes (the operational gap
   analysis's "actuation" and "real execution"), and grounding them in a real Repository Intelligence.

So the verdict: **Human Interaction completes the human-in-the-loop architecture and, with Engineering
Intelligence and Execution Actuation, closes the last *architectural* gap between a governance skeleton
and a safe autonomous engineering control plane.** What remains before Nexus operates as one is not a
missing foundational subsystem but the *implementation* of these ratified designs plus the *grounding*
(Repository Intelligence) and *identity* (approver authorization) extensions the designs already name.
The architectural picture is, for the first time, complete.

---

# Certification

The Human Interaction architecture is **internally consistent, invariant-preserving
(INV-07/13/14/16/17/25/26/28/29/30/31/32/34/36/39), deterministic-on-replay, auditable,
provider-independent, fail-closed, and complete for its defined scope**, with all frontier concerns
named and deferred (`13`). It amends no ADR, contract, or invariant, adds no code, and contradicts
nothing in the existing architecture; it specifies the canonical human-facing surface the approval
model already delegates to, and unifies clarifications, approvals, notifications, conversations,
escalations, and reviews under one governed, channel-independent subsystem.

**Recommendation: ratify and freeze the core.** A future team may build the `nexus_human_interaction`
subsystem directly against these documents. With Engineering Intelligence, Execution Actuation, and
Human Interaction ratified, the autonomous-engineering architecture is complete; the next epoch is
**implementation** — building these three subsystems and grounding them in a full Repository
Intelligence — not further foundational design.
