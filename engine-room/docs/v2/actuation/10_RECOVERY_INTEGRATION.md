# Recovery Integration

Status: Target Architecture (design only)

---

# Purpose

This document answers the exercise's question directly:

> How does Recovery interact? Can Recovery resume, reattach, recreate, restart — or only recommend?

**Answer: Recovery *decides*; Orchestration *directs*; Actuation *enacts*. Actuation exposes four
mechanisms — resume, reattach, recreate, restart — but chooses among them for none of them.**

---

# The three-role split (unchanged from the platform spine)

```
Supervision   observes the failure fact, derives health, RECOMMENDS intervention   (INV-23)
   │
Recovery      classifies the failure and DECIDES the strategy                       (INV-22)
   │
Orchestration DIRECTS the chosen action; owns pause/resume/cancel control           (INV-23)
   │
Execution     ENACTS the directed mechanism against the real environment            (this layer)
Actuation
```

Actuation is at the **enact** end. It never sits in the **decide** middle. This mirrors how RM
enacts control transitions on a governance/approval signal without deciding them (`../runtime/18`
§7, `../runtime/20` G-7).

---

# The four mechanisms Actuation exposes

Recovery's strategy set (`../19_RECOVERY.md`: Retry, Resume, Checkpoint Restore, Switch Runtime,
Rollback, …) maps onto four actuation-level mechanisms. Actuation makes each *possible*; Recovery
selects which:

| Mechanism | What Actuation does | Preserves | Enabled by |
|---|---|---|---|
| **resume** | continue a Session from its last valid checkpoint | progress + evidence (INV-18/22) | Actuator-declared resume capability (`../runtime/20` G-4); checkpoint ref (`04`) |
| **reattach** | bind a **new** Runtime Session attempt to an **already-live** Session | the live environment itself (no re-provision) | the Session outliving the attempt (`04` §Session vs Runtime Session) |
| **recreate** | provision a **fresh** Environment (new isolation), then a new Session | prior Evidence Candidates (referenced, not lost) | Environment lifecycle (`03`) |
| **restart** | open a **fresh** Session in the **same** Environment | the Environment; discards in-session state | Session lifecycle (`04`) |

- **resume** and **reattach** preserve the most (continue live/checkpointed work) — the INV-22 ideal
  of recovering rather than restarting.
- **recreate** and **restart** are the fallbacks when the environment or session is unsalvageable —
  but even then, previously produced Evidence Candidates are never discarded (INV-22, `09`).

---

# "Switch runtime" and rollback

- **Switch runtime** (Recovery's runtime failover, `../19` §Runtime Failover) is a **recreate on a
  different runtime**: Orchestration re-nominates candidates, RM allocates a different runtime, and
  Actuation provisions a fresh Environment for it (`03`). Actuation performs the provisioning; it
  never *chooses* the different runtime (INV-37).
- **Rollback** (Recovery, domain-specific) is enacted by Actuation as governed Workspace/environment
  actions (e.g. `git revert`, restore a checkpointed state) — permission-checked (`06`) and gated
  where consequential (`07`). Actuation performs the rollback; Recovery decides it is warranted.

---

# Recovery never restarts from the Goal — and Actuation makes that literal

INV-22: *Recovery recovers; it never restarts from the Goal, never changes the Goal or Plan.* At the
actuation boundary this is concrete:

- A reattach/resume continues **live or checkpointed work** — not a re-derivation from intent.
- A recreate/restart re-provisions the **environment**, not the plan; the same Work Package is
  re-driven, and prior Evidence Candidates survive.
- Actuation has **no path back to the Goal**: it receives a Work Package (INV-09/19), never a Goal,
  so it *cannot* restart from intent even if asked. The architecture makes the invariant
  unbreakable at this layer.

---

# The reattach window (the payoff of the Session model)

Because a Session can be **`Detached` yet alive** (`04`), Actuation can hold a live environment for a
bounded **reattach window** after an attempt ends without success:

```
attempt n fails ──► Session → Detached (kept alive, still walled)  ──► actuation.session_suspended
        │                                                                     │
   Recovery decides: reattach                                                 │ within the window
        ▼                                                                     ▼
attempt n+1 (new Runtime Session) ──► reattach ──► same live Session ──► actuation.session_resumed
```

- The window is **bounded** and **governed** — a kept-alive Session is not a leak; it is recorded,
  still within its isolation surface, and torn down if the window lapses (`09`, `11`).
- Whether to keep the Session and how long is a **Recovery/Strategy** input; Actuation is the
  mechanism (`04`). This is the capability the one-attempt Runtime Session cannot provide and the
  reason Actuation models the Session separately.

---

# What Recovery may direct, and what it may not

| Recovery MAY direct Actuation to… | Recovery / Actuation may NOT… |
|---|---|
| resume from a checkpoint | have Actuation *decide* to resume on its own |
| reattach to a live Session | have Actuation *choose* a different runtime (INV-37) |
| recreate / restart the environment | restart from the Goal (INV-22) |
| roll back via governed actions | bypass permissions or approval (`06`/`07`) |
| keep or tear down a Detached Session | discard preserved Evidence (INV-22) |

Every directed action is permission-checked (`06`), gated where consequential (`07`), and recorded
(`08`) — recovery does not get a privileged path around governance.

---

# North Star

Recovery chooses; Actuation performs. The platform can resume checkpointed work, rejoin a
still-running session, rebuild a broken environment, or start a fresh one — four real mechanisms —
and Actuation offers all four while deciding none, never restarting from intent and never stepping
around a permission or a gate.
