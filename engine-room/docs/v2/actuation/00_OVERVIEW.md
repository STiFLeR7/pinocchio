# Execution Actuation — Overview

Status: Target Architecture (design only)

---

# Purpose

Execution Actuation is the **realization substrate behind the Runtime Adapter boundary**.

It is where the platform stops *preparing* to act and actually *acts* inside an external engineering
environment — but only ever to carry out work that has already been decided, selected, and
prepared upstream.

It models the external world the platform operates on (Environment, Workspace, Session), provides
the governed primitives that operate it (filesystem, git, terminal, process, MCP), enforces the
permission envelope on every action, and emits an auditable action stream — so that the concrete
"how" of touching a real environment is specified once, shared across all runtimes, and uniformly
governed, instead of being re-invented inside every adapter.

---

# The line the Runtime layer drew, and where Actuation begins

```
Orchestration      nominates candidate runtimes                     (INV-37)
   │
Runtime Manager    allocates a Runtime Session (one attempt binding) (../runtime/02)
   │
Execution Engine   drives the Runtime Session through a Runtime Adapter
   │
Runtime Adapter    the nine-concern conceptual contract              (../runtime/03 §2)
   │  ────────────────  RUNTIME ADAPTER BOUNDARY  ────────────────
   ▼
[ Execution Actuation ]  operates the External Environment
   │   • Environment / Workspace / Session model
   │   • filesystem / git / terminal / process / MCP primitives
   │   • per-action permission enforcement
   │   • actuation.* event stream + Evidence Candidates
   ▼
External Environment      (Claude Code, shell, Docker, browser, MCP, remote…)
   │
   ▼  Evidence Candidates + actuation.* events
Supervision (observes) ─► Validation (judges completion, INV-20)
```

Above the boundary is unchanged and specified. Below it is Actuation.

---

# Is the prompt's placement correct?

The exercise proposed:

```
Goal → … → Runtime → Execution → Execution Actuation → External Environment → Validation
```

**Corrected.** Runtime is not a pipeline stage *before* Execution; it is a capability Execution
*uses*. Selection (Orchestration) and allocation (Runtime Manager) produce a Runtime Session; the
Execution Engine drives that session; the drive is realized, *through the Runtime Adapter*, by
Execution Actuation operating the external environment. So Actuation does not sit *after* Execution
as a peer stage — it sits **beneath the adapter boundary that Execution already crosses**. The
prompt's intuition (Actuation is the last thing before the external environment, and its outputs
feed Validation) is right; its linear ordering is refined to place Actuation behind the adapter, not
between Execution and Validation.

---

# Inputs

Actuation is invoked by an Actuator (satisfying a Runtime Adapter) with, all **by
value/reference**:

| Input | Origin | Carries |
|---|---|---|
| **Runtime Session (ref)** | Runtime Manager (`../runtime/02`) | the allocated runtime, attempt ordinal, correlation, checkpoint refs |
| **Work Package (ref)** | embedded in the Execution Package (INV-09/19) | *what* to perform — never a Goal or raw request |
| **Isolation profile** | rendered config (`../runtime/17` §2) | the environment's sandbox/filesystem/network posture |
| **Permission envelope** | derived from declared requirements + resolved Policy bundle (`06`, `../runtime/18`) | the permitted action classes |
| **Secret references** | injected handles, never values (`../runtime/17` §3) | scoped credential handles resolved from `.env` |
| **Recovery directive (opt.)** | Recovery via Orchestration (`10`) | resume / reattach / recreate / restart |

Actuation never receives a Goal, a Plan, raw operator text, or a completion verdict.

---

# Outputs

| Output | Consumer | Notes |
|---|---|---|
| **actuation.* events** | Event log → Supervision | raw action facts; session state is a projection (INV-13/14) |
| **Evidence Candidates** (by ref) | collected on the Runtime Session → Validation | files, diffs, command results, screenshots — referenced, never embedded (INV-12/27) |
| **Session state** (projection) | Recovery / Operator (read-only) | live/detached/terminated; a projection of the log |
| **Typed failures** | Recovery (`09`) | class + owner; Actuation reports, never decides recovery |

Actuation does **not** output validated results, plans, knowledge, recovery decisions, or a claim
of success.

---

# Dependency direction

```
nexus_actuation → { nexus_core, nexus_infra }        (only)
        ▲
        │ consumed by (provider-specific, behind the boundary)
        └── Runtime Adapters / Actuators

RM core  ──drives generically──►  Runtime Adapter  ──realized on──►  nexus_actuation
   (unchanged; still knows only the adapter contract, never Actuation internals)
```

- Actuation imports no upstream layer and no RM core. It is imported only by the provider-specific
  adapter/actuator code that already lives behind the Runtime Adapter boundary (`../runtime/03` §3).
- RM core stays generic and unchanged: it never branches on a provider and never learns Actuation's
  internals. "Everything upstream continues working unchanged" holds by construction.
- Actuation persists and emits only through the Phase-2 substrate (event store, bus, repositories,
  observability) — it invents no new persistence and does not modify `nexus_infra`, the pattern
  every prior layer followed.

---

# Canon glossary

| Term | Meaning |
|---|---|
| **Actuator** | provider-specific driver operating one environment kind; satisfies a Runtime Adapter using the Actuation substrate. |
| **Environment** | the isolated locus of actuation (local, container, remote, pod). |
| **Workspace** | the filesystem/repository scope inside an Environment. |
| **Session** | the live, long-lived, reattachable interaction; distinct from the per-attempt Runtime Session. |
| **Actuation Command** | a single governed action issued into a Session (`02`). |
| **Permission Envelope** | the permitted action classes for a Session (`06`). |
| **Evidence Candidate** | a produced output referenced by id, promoted to Evidence only by Validation (INV-12/20). |

---

# North Star

Every layer above decided what should happen and where. Execution Actuation is where the platform
finally reaches into the real world and does it — safely, within a permission envelope, on the
record, and never deciding for itself what, which, or whether.
