# The Execution Actuation Layer

Status: Target Architecture (design only)

---

# What Execution Actuation is

Execution Actuation is the subsystem that operates external engineering environments on behalf of
already-decided, already-selected, already-prepared work.

It is the platform's **hands**: the layer that launches Claude Code in a repository, opens a shell,
writes a file, runs a command, commits to git, drives a browser, or calls an MCP tool — each action
scoped to a permission envelope, recorded as an event, and producing artifacts that Validation will
judge.

It is deliberately the **lowest** cognitive point in Nexus. Everything above it thinks; Actuation
acts. It holds no operational intelligence, exactly as Execution holds none (`../08_EXECUTION.md`):
the difference is that Execution is the *engine* that drives a runtime, while Actuation is the
*substrate* that realizes what touching a real environment concretely means.

---

# What Execution Actuation is NOT

- **Not Runtime selection.** Orchestration nominates; RM allocates (INV-37). Actuation operates the
  runtime it is handed; it never chooses one.
- **Not the Runtime Manager.** RM prepares and owns the per-attempt Runtime Session (`../runtime/02`).
  Actuation realizes it and owns the *live environment*, a different and longer-lived object (`04`).
- **Not Execution (the engine).** The Execution Engine decides the sequence of interactions for a
  Work Package. Actuation carries out each interaction. It never plans the interactions (INV-04).
- **Not Planning / Context / Engineering Intelligence.** Actuation performs; it never decides what
  work exists, what context is needed, or how the work should proceed.
- **Not Supervision.** Actuation emits raw action events; only Supervision derives Observations and
  health, and recommends intervention (INV-11/23).
- **Not Validation.** Actuation produces Evidence Candidates; only Validation promotes them to
  Evidence and renders completion (INV-12/20/21).
- **Not Recovery.** Actuation exposes resume/reattach/recreate/restart *mechanisms*; Recovery
  decides which to use (INV-22, `10`).
- **Not Governance.** The Policy Engine evaluates policy; Actuation *enforces* the resolved envelope
  and *pauses* for approval, deciding neither (INV-28/29, `07`).

---

# Responsibilities

Execution Actuation is responsible for:

- **environment lifecycle** — create, configure, attach, suspend, terminate, and destroy
  Environments and Sessions (`03`, `04`);
- **workspace operation** — governed filesystem and git operations within a Workspace (`05`);
- **action execution** — issuing governed Actuation Commands (terminal, tool, MCP call, process
  control) into a Session (`02`);
- **permission enforcement** — checking every action against the Session's Permission Envelope
  before it happens, and denying otherwise (`06`);
- **secret handling** — injecting credential *references* at configure-time, redacting values at the
  stream/artifact edge, revoking at teardown (`11`, honoring `../runtime/17`);
- **artifact surfacing** — emitting produced outputs as Evidence Candidates by reference (`08`,
  INV-12);
- **event emission** — recording every governed action as an immutable, correlated `actuation.*`
  event (`08`, INV-13/39);
- **failure reporting** — surfacing typed failures with class and owner (`09`);
- **recovery enactment** — carrying out a resume/reattach/recreate/restart directive (`10`).

Execution Actuation **never**:

- decides what work to perform, or in what order (Execution/Planning own that);
- selects or allocates a runtime (Orchestration/RM);
- evaluates governance policy or decides an approval (Policy Engine/approver);
- observes health or recommends intervention (Supervision);
- determines completion or grades an artifact (Validation);
- decides recovery (Recovery);
- writes Knowledge (Knowledge Engine);
- stores secret values or prints them (`.env` is the sole source — `../runtime/17` §1).

---

# The actuate pipeline

For one Work Package driven inside one Runtime Session, Actuation runs this pipeline. It is
event-sourced and deterministic on replay (INV-13/14/17).

```
Attach / Provision        create or reattach the Environment + Session (03, 04);
   │                      render the isolation profile (../runtime/17 §2)
   ▼
Open Workspace            bind the filesystem/repository scope (05)
   │
   ▼
Per interaction (driven by the Execution Engine):
   ┌───────────────────────────────────────────────┐
   │  Check Permission Envelope (06)                │  ← deny → actuation.command_denied, no action
   │      │ allow                                   │
   │      ▼                                         │
   │  Enact Action (terminal / fs / git / MCP …)    │  → actuation.command_executed
   │      │                                         │
   │      ▼                                         │
   │  Surface outputs as Evidence Candidates (08)   │  → actuation.artifact_generated
   │      │                                         │
   │      ▼                                         │
   │  Emit actuation.* events (correlated)          │
   └───────────────────────────────────────────────┘
   │
   ▼
Suspend or Terminate      detach (keep alive) or tear down (11 §teardown)
   │
   ▼
Evidence Candidates + typed terminal status  → Runtime Session → Supervision / Validation
```

Actuation never decides the *content* of the per-interaction loop — the Execution Engine, driving
the Work Package, decides what interactions to issue. Actuation decides only whether each is
*permitted* and how it is *carried out and recorded*.

---

# The load-bearing discipline: operate, never decide

Every responsibility above is an *operating* act. The moment a step would decide *what* to run,
*which* runtime, *whether* it succeeded, or *what to do next*, it has left Actuation:

| If a step would… | it belongs to |
|---|---|
| choose the next interaction | Execution Engine (the Work Package drives it) |
| choose a different runtime on failure | Recovery + Orchestration (INV-22/37) |
| decide the work is complete | Validation (INV-20) |
| decide an action is allowed by policy | Policy Engine (INV-28) — Actuation only *enforces* the verdict |
| interpret output quality | Validation / Supervision |

This mirrors the Runtime Adapter litmus test (`../runtime/03` §6): an actuator "may change *where*
and *how* already-decided work is hosted; it may never change *what* runs or *whether* it
succeeded." Actuation is that rule made into a subsystem.

---

# North Star

Execution Actuation is the disciplined hand of Nexus.

It reaches into real environments and performs exactly the governed actions it is asked to perform —
recording every one, exceeding no permission, and claiming nothing about whether the work was good.
Thinking happens above. Here, work happens.
