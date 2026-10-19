# Execution Actuation — Architecture Review & Ratification

Status: Design review (design only). No implementation, no ADR/contract/invariant change.

This review evaluates the Execution Actuation architecture (`README`, `00`–`13`) for correctness,
completeness, and readiness, and answers the ratification questions. Its purpose is to certify that a
future team can build the layer **without making new architectural decisions**, and to state whether
Actuation completes Nexus' ability to safely operate external environments or whether further
subsystems are still required.

---

# 1. Dependency direction

**Verdict: sound and structurally enforced.**

```
nexus_actuation → { nexus_core, nexus_infra }   (only)
        ▲
        │ consumed by provider-specific Actuators (behind the Runtime Adapter boundary)
RM core ── drives generically ─► Runtime Adapter ── realized on ─► nexus_actuation
   (unchanged; still knows only the adapter contract)
```

- Actuation imports no upstream layer and no RM core; it is consumed only by the provider-specific
  Actuator code that already lives behind the Runtime Adapter boundary (`../runtime/03` §3). This
  matches every layer built so far (`nexus_knowledge`, `nexus_runtime` → `{nexus_core, nexus_infra}`).
- RM core stays generic and unchanged — it never branches on a provider and never learns Actuation's
  internals (`00`). "Everything upstream continues working unchanged" holds by construction.

---

# 2. Non-duplication of the Runtime layer

**Verdict: additive; consolidates rather than competes.**

This was the central risk, and it is addressed head-on:

- The Runtime **Adapter** contract, the **Runtime Session**, runtime **selection**, and the
  **`runtime.*`** events are unchanged. Actuation is the shared substrate the Actuators are *realized
  on* (`README`, `02`).
- Granularity is distinct: `runtime.*` events model **session lifecycle**; `actuation.*` events model
  **individual governed actions** inside the environment (`08`). No event is duplicated.
- Security (`../runtime/17`) and governance (`../runtime/18`) rules are **honored and enforced at
  finer granularity** (per action), not redefined (`06`/`07`/`11`).
- The genuine additions are exactly what the Runtime layer deliberately omitted: first-class
  `Environment`/`Workspace` objects, and a **long-lived, reattachable Session** distinct from the
  one-attempt Runtime Session (`04`) — which the Runtime docs explicitly scope out (`../runtime/02`
  §9).

---

# 3. Boundary correctness

**Verdict: every seam is one-directional and decides nothing it should not.**

- **Execution** decides the interactions; Actuation carries them out (INV-04). ✔
- **Orchestration/RM** select and allocate; Actuation operates what it is handed (INV-37). ✔
- **Supervision** observes/recommends; Actuation emits raw facts (INV-11/23). ✔
- **Validation** decides completion from Evidence; Actuation produces Evidence Candidates (INV-12/20).
  ✔
- **Recovery** decides continuation; Actuation exposes resume/reattach/recreate/restart mechanisms
  (INV-22, `10`). ✔
- **Policy Engine** evaluates; Actuation enforces the envelope and pauses for approval (INV-28/29,
  `06`/`07`). ✔
- **Knowledge** — Actuation writes none; its events feed Supervision→Reflection→Knowledge indirectly.
  ✔

The load-bearing discipline (operate, never decide) is the actuation form of the adapter litmus test
(`../runtime/03` §6): may change *where/how* work is hosted; never *what* runs or *whether* it
succeeded (`01`).

---

# 4. Object model completeness

**Verdict: four nouns absorb every named concept.**

`Environment`, `Workspace`, `Session`, `Actuator` (+ `Actuation Command`, `Permission Envelope`)
canonically represent repositories, workspaces, terminals, CLI sessions, IDE instances, and remote
machines (`03` mapping table). No named physical concept lacks a home; no object overlaps another's
responsibility (INV-02).

---

# 5. Security & governance

**Verdict: strong; hardest where it matters most.**

- The `.env` secret spine is inherited verbatim; Actuation holds only references, redacts at every
  edge, and revokes at teardown (`11`, `../runtime/17`).
- Least privilege is enforced **per action** via the Permission Envelope; default-deny; fail-closed
  (`06`, INV-30).
- Blast radius is physically bounded by the Environment's isolation surface; consequential/irreversible
  actions are gated (`07`/`11`).
- Every governed action — permitted or denied — is an immutable, correlated audit event (`08`,
  INV-31/39).

---

# 6. Determinism & event-sourcing

**Verdict: preserved.**

State (Environment/Session/Workspace) is a projection of the `actuation.*` log (INV-13/14);
consumption is idempotent (INV-16); non-deterministic values live only in payloads (INV-17);
identifiers are deterministic (mirroring `../runtime/02` §3). Replay reconstructs actuation state
exactly.

---

# 7. Readiness

**Verdict: ready to implement against fixed seams.**

Reuses the Phase-2 substrate (event store, bus, repositories, observability) and the Runtime
security/governance rules unchanged. Every open item (`13`) is a named, non-blocking extension; the
core needs no new architectural decision. The high-urgency gaps are a seam formalization (G-2), a
capacity model shared with the Runtime layer (G-4), and a platform-wide human-interaction channel
(G-9) — none reopens an ADR.

---

# Ratification questions

### 1. Can Execution Actuation be implemented without architectural ambiguity?
**Yes.** The subsystem, placement behind the adapter boundary, object model, the actuate pipeline,
permissions, governance, events, failures, recovery mechanisms, security, and extensibility are all
specified (`00`–`12`). Open items are deferred and non-blocking (`13`).

### 2. Does it preserve the Runtime, Execution, Validation, and Recovery architectures?
**Yes.** It changes none of them. It is the shared realization substrate behind the (unchanged)
Runtime Adapter boundary, honoring INV-04/09/12/20/22/37 and the runtime security/governance rules
(§2, §3).

### 3. Does it preserve provider and runtime independence?
**Yes — structurally.** The substrate reasons only in Environment/Workspace/Session/Command/permission
/event terms (INV-32); all provider knowledge lives in Actuators; no substrate branch on a provider
is permitted (`12`).

### 4. Does it preserve determinism, auditability, and the secret spine?
**Yes.** Event-sourced projections (INV-13/14/17), every governed action audited (INV-31/39), `.env`
single-source with references-only and edge redaction (`11`).

### 5. Does it change any existing engine, contract, ADR, or invariant?
**No.** It adds a subsystem consumed only by provider-specific adapter code; it modifies no engine,
contract, ADR, or invariant. Previous programs remain green by construction.

---

# Does Execution Actuation complete Nexus' ability to safely operate external environments?

**It completes the *mechanism*. It does not, by itself, complete *unattended* safe operation — one
shared subsystem remains required.**

With Actuation defined, Nexus has, for the first time, a specified, governed, provider-independent way
to actually *do* work in the outside world: model the environment, open and hold (and reattach) a live
session, operate the filesystem and git within a permissioned workspace, gate the irreversible, redact
every secret, record every action, and enact the recovery someone else chose. Combined with the
existing Runtime layer above it and the (design-complete) Engineering Intelligence that decides *how*
work should proceed, the platform's *doing* spine is now architecturally whole:

```
Engineering Intelligence (decide how)  →  Runtime (select/allocate)  →  Execution (drive)
     →  Execution Actuation (operate the real environment)  →  Validation (judge)
```

Two frontiers remain before the reference request — *"open Claude Code in D:/project_x, fix the bug,
validate, commit, report back"* — runs unattended end to end:

1. **The Human-Interaction channel (blocking, shared).** Actuation *places and enacts* approval gates
   (`07`) and Engineering Intelligence *proposes* them (`../engineering/08`), but the channel through
   which a human grants a gated commit/push or answers a clarification is a platform-wide subsystem
   that does not yet exist (`13` G-9, `../engineering/14` G10). Without it, gated autonomy cannot
   complete the "commit it" and "report back" steps unattended. This is the single remaining blocker
   for the end-to-end vision, and it is shared by Actuation, Engineering Intelligence, Intent
   Resolution, Recovery, and Governance — it should be designed next.

2. **Repository Intelligence as a full subsystem (grounding).** Actuation operates a Workspace; it does
   not *understand* the repository. Engineering Intelligence's decisions and Validation's rigor are
   only as grounded as the repository facts available (`../engineering/10`, `../engineering/14` G2).
   This does not block Actuation, but it bounds how well the platform can *decide* what to actuate.

So the honest verdict: **Execution Actuation completes the platform's ability to safely *perform*
governed actions in external engineering environments — the "hands" the operational analysis and the
Engineering Intelligence review both named as missing.** Together with Engineering Intelligence (the
"decision"), it closes the two largest holes between a governance skeleton and a real operator. What
remains is one **shared** subsystem — the Human-Interaction channel that enacts the approval and
clarification gates both layers already define — plus the deeper grounding of a full Repository
Intelligence subsystem.

---

# Certification

The Execution Actuation architecture is **internally consistent, invariant-preserving
(INV-04/09/12/13/14/17/20/22/27/28/29/30/31/32/36/37/39), deterministic, auditable,
provider-independent, and complete for its defined scope**, with all frontier concerns named and
deferred (`13`). It amends no ADR, contract, or invariant, adds no code, and contradicts nothing in
the Runtime, Execution, Validation, or Recovery architectures; it specifies the shared realization
substrate behind the (unchanged) Runtime Adapter boundary.

**Recommendation: ratify and freeze the core.** A future team may build the `nexus_actuation`
subsystem directly against these documents. Sequence the **Human-Interaction channel** design next —
it is the shared, highest-leverage subsystem that lets the approval and clarification gates defined by
both Actuation and Engineering Intelligence actually complete unattended engineering work.
