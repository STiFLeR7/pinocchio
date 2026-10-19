# 01 — Runtime Manager

**Status:** design only. Defines the Manager's responsibilities, the **preparation
pipeline** (the spine of the subsystem), and the hard boundaries that keep it from
absorbing execution, planning, validation, or recovery.

---

## 1. What the Runtime Manager is

The Runtime Manager is the control plane for runtimes. It is a **coordinator and
preparer**, structurally analogous to the Orchestration Service (which coordinates a
Plan) and the Harness Service (which compiles a package): it consumes immutable
upstream outputs, makes deterministic decisions where decisions are deterministic,
delegates the non-deterministic act (running) to something else, persists through
Phase 2, and emits events.

It is **not** a runtime. It holds no shell, opens no socket of its own, runs no model.
Those live behind adapters (`03`).

## 2. Responsibilities (normative)

1. **Discovery** — know which runtimes exist, via the Registry view (`04`).
2. **Registration** — accept runtime registrations (adapters advertising a Runtime
   Descriptor) into the Registry view; never duplicate the Harness Registry's
   ownership of availability/health (INV-36).
3. **Capability matching** — confirm a candidate's advertised capabilities satisfy the
   manifest's required capabilities; record optional/unsupported (`05`).
4. **Health** — read liveness/availability from the Registry; probe through the adapter
   where a runtime exposes a health signal; never treat telemetry as authoritative
   state.
5. **Selection & allocation** — choose exactly one runtime from the eligible candidates
   under policy, then reserve/allocate it (`06`). **Allocation lives here.**
6. **Session creation** — create the Runtime Session that binds the Execution Package
   to the allocated runtime (`02`).
7. **Configuration** — translate the package's declarative requirements into the
   adapter's configuration shape (env, working dir, limits, isolation profile) without
   leaking provider specifics into RM core.
8. **Preparation → handoff** — drive the session to `Ready` and hand it to the
   Execution Engine.
9. **Supervision** — while the engine runs the work: stream output (`08`), track
   progress (`12`), enforce timeouts (`10`), honor cancellation (`09`), collect
   artifacts (`13`), and pause for approval (`14`).
10. **Teardown** — release the allocation and destroy the session (`07`), regardless of
    outcome.
11. **Telemetry** — emit runtime/session metrics and traces (`16`).

## 3. Boundaries (what RM must never do)

| RM never… | Because |
|---|---|
| plans or re-plans work | Planning owns decomposition (Phase 3); RM receives a finished Work Package (INV-09) |
| orchestrates / re-orders work | Orchestration owns coordination (Phase 5); RM prepares one package at a time |
| edits the repositories it reads from | RM reads Packages/Manifests/Registry; it writes only its own session state + events |
| validates execution outcomes | Validation owns verdicts from Evidence (INV-20); RM only reports *process ended* |
| performs recovery | Recovery owns retry/rollback/abort selection; RM surfaces failures as events (`11`) |
| updates Knowledge / reflects | Knowledge & Reflection are downstream of validated outcomes |
| invokes AI reasoning directly | RM issues no prompts and makes no model decisions; an *adapter* may front an AI runtime, but the reasoning happens inside that runtime, not in RM |
| decides approvals | RM *pauses* for approval using ADR-004's taxonomy; the decision is the approver's (`14`) |
| embeds secrets | secrets are passed by injected reference to the adapter, never embedded in packages, events, or logs (`17`) |

The litmus test: **if removing the line of reasoning would change *what* runs or
*whether* it succeeded, it does not belong in RM.** RM only changes *where* and *how*
the already-decided work is hosted.

## 4. The preparation pipeline

RM processes one Execution Package through a deterministic pipeline. Only the runtime's
*execution* is non-deterministic; preparation is reproducible given identical inputs and
identical Registry state.

```
Execution Package (+ Manifest, + Runtime Request)
   │
   ▼  1. VALIDATE INTAKE      package/manifest well-formed; required capabilities present;
   │                             candidates non-empty; correlation resolvable
   ▼  2. RESOLVE CANDIDATES    read candidate_harness_refs → Registry descriptors (04)
   │
   ▼  3. MATCH CAPABILITIES    keep candidates whose advertised caps ⊇ required caps (05)
   │
   ▼  4. FILTER HEALTH         drop unavailable/unhealthy candidates (Registry, INV-36)
   │
   ▼  5. APPLY POLICY          governance: allowed runtimes, cost ceiling, isolation (18)
   │
   ▼  6. APPROVAL CHECKPOINT   if policy requires approval, PAUSE → wait → resume (14)
   │
   ▼  7. SELECT                choose one runtime deterministically from the survivors (06)
   │
   ▼  8. ALLOCATE              reserve → allocate in ResourceAllocationState (06)
   │
   ▼  9. CREATE SESSION        bind package ⇄ runtime; assign identities (02)
   │
   ▼ 10. CONFIGURE             render adapter config (env/cwd/limits/isolation) (17)
   │
   ▼ 11. READY                 session reaches Ready; emit runtime.ready
   │
   ▼ 12. HANDOFF               pass Ready session to the Execution Engine
   │
   ▼ 13. SUPERVISE             stream / progress / timeout / cancel / artifacts / approval
   │
   ▼ 14. RELEASE + DESTROY     free allocation; destroy session; emit terminal events
```

Steps 1–11 are **preparation** (RM's deterministic core). Steps 12–14 are
**supervision/teardown** (RM's control-plane role around an execution it does not
perform). A failure at any step short-circuits to RELEASE + DESTROY with a typed error
(`11`) and a `runtime.failed` event — never a silent default.

## 5. Determinism

Like every prior layer, RM's *preparation* must be deterministic: given the same
Execution Package, the same Runtime Request, and the same Registry snapshot, RM selects
the same runtime, allocates with the same identifiers, and emits the same preparation
event sequence. Sources of non-determinism are confined and injected:

- **Wall-clock** → an injected timestamp source; recorded only in event payloads
  (INV-17). Session value objects carry no timestamp.
- **The runtime's behavior** (its stdout, duration, exit) → inherently
  non-deterministic, but it is *observed*, not *decided*; it enters the system only as
  recorded events, exactly like any external fact (INV-17).
- **Registry state** (which runtimes are healthy) → an explicit input, snapshotted at
  intake so a single preparation reasons over a stable view.

Identifiers (session id, allocation id, event ids) are pure functions of the package
identity and node key — no clock, no counter, no randomness — so a replay reproduces
the same names (`02` §Identifiers).

## 6. Relationship to the Execution Engine (Phase 8)

RM stops at **handoff** of a `Ready` session and resumes at **supervision**. The
Execution Engine is the thing that, through the adapter, actually starts the runtime
process, drives the Work Package, and produces Evidence Candidates. The clean seam is
the Runtime Session: RM owns its lifecycle and allocation; the engine owns the *running*
of the work *within* it. This is the same separation the whole platform is built on —
preparation vs performance — applied one final time.
