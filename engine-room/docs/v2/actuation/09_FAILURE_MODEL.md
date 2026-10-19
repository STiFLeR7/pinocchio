# Failure Model

Status: Target Architecture (design only)

---

# Purpose

This document defines how Actuation **reports failure** — as typed facts with a class and an owner —
and establishes that Actuation **never decides recovery**. It exposes what failed; Recovery decides
what happens next (`10`, INV-22).

---

# The rule: report, never decide

Like Execution (`../08_EXECUTION.md` §Failure Handling), Actuation **reports failures and does not
decide recovery**. It surfaces:

- the **failure class** (what kind of failure),
- the **owner** (which layer must act),
- the **last valid checkpoint** (INV-18),
- the **artifacts produced so far** (Evidence Candidates, never discarded),
- the **Session/Environment state** (a projection of the log).

It emits `actuation.failed` (`08`) with the class and owner — **never a secret value** (`11`) — and
holds the Session in a terminal/awaiting state. It chooses no retry, no runtime switch, no restart.

---

# Failure classes

Actuation classifies failures so Recovery can select a strategy (Recovery's failure taxonomy,
`../19_RECOVERY.md`). The classes are provider-independent (INV-32); the Actuator maps a provider's
concrete error onto one of them.

| Class | Examples | Typical owner |
|---|---|---|
| **environment failure** | container failed to start; namespace/isolation setup failed; remote host unreachable | Recovery → recreate/restart (`10`) |
| **session failure** | CLI process crashed; connection dropped; browser driver died | Recovery → reattach/restart |
| **command failure** | a permitted command exited non-zero; a tool call errored | Execution/Recovery (may be expected work output, not an actuation fault) |
| **permission denial** | a command outside the envelope was attempted (`06`) | not a fault — a governed denial; surfaced, work continues or Recovery escalates |
| **isolation/security failure** | required credential unresolved; isolation surface unbuildable | **refuse** (fail-closed, `11`); Recovery/Governance |
| **timeout** | execution/inactivity/wait limit exceeded (`../runtime/10`) | Recovery per Strategy |
| **resource exhaustion** | disk full; OOM; quota exceeded | Recovery / Orchestration (capacity, `../runtime/20` G-3) |
| **teardown failure** | credential revocation or cleanup failed | surfaced anomaly (`11` §teardown); operator attention, capacity still released |

---

# Fail-closed is the default response to a security gap

Consistent with runtime security (`../runtime/17` §5) and governance (`../runtime/18` §6): a missing
credential, an unbuildable isolation surface, or an unresolved required grant **refuses the Session**
before any action. There is no degraded-but-acting state. The refusal is a typed `actuation.failed`
carrying the *class* — never the missing secret's value.

---

# Failures preserve, never discard

Actuation failures never destroy progress that Recovery may reuse (INV-22 progress/evidence
preservation):

- **Evidence Candidates already produced remain valid** and referenced (INV-12) — a failure does not
  invalidate a diff already written or a test result already captured.
- **The last checkpoint is preserved** and referenced (INV-18), so a resume can continue from it
  rather than restart (`10`).
- **A live Session may be kept** (`Detached`) rather than killed, so Recovery can choose reattach
  (`04`, `10`).

What is preserved vs. torn down is a *mechanism* Actuation exposes; **which to use is Recovery's
decision**.

---

# Teardown always runs — even on failure

Security ends at `Destroyed`, not at failure (`../runtime/17` §7). On every terminal failure path,
teardown runs: credentials revoked, injected env scrubbed, ephemeral profiles/workspaces removed,
containers torn down, processes killed. A teardown that itself fails is a **surfaced typed anomaly**
(`08` `actuation.failed`, class = teardown), never a swallowed one — and the allocation is still
released so capacity does not leak (`../runtime/17` §7).

The exception is a deliberately **kept-alive** `Detached` Session for reattach (`04`, `10`): that is
not a leaked environment but a governed, recorded, still-walled one, awaiting a bounded reattach
window; if the window lapses, teardown runs.

---

# Relationship with the layers that act on failure

| Layer | Role on failure |
|---|---|
| **Supervision** | observes the `actuation.failed` fact; derives health; **recommends** intervention (INV-23) |
| **Recovery** | classifies further; **decides** the strategy — retry/resume/reattach/recreate/switch/escalate/abort (INV-22, `10`) |
| **Orchestration** | **directs** the chosen action; owns pause/resume/cancel control (INV-23) |
| **Execution Actuation** | **enacts** the directed mechanism against the environment (`10`) |
| **Validation** | may itself *trigger* recovery when evidence is insufficient (INV-20/21) |

Actuation is the reporter and the enactor at the ends of this chain — never the decider in the
middle.

---

# North Star

When something breaks inside a real environment, Actuation says exactly what broke, keeps everything
worth keeping, tears down everything that must not leak, and waits. It never guesses the fix — it
reports the failure and enacts the recovery someone else chose.
