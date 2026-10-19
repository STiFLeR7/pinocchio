# Workspaces

Status: Target Architecture (design only)

---

# Purpose

This document defines the **Workspace** — the filesystem/repository scope inside an Environment — and
establishes that filesystem and git operations are **owned by Actuation** as governed primitives,
scoped to a Workspace and checked against the Permission Envelope.

---

# What a Workspace is

A **Workspace** is the bounded filesystem and version-control scope a Session operates within: a
repository checkout, a working directory, a mounted volume. It is the unit on which filesystem and
git permissions are granted and enforced (`06`).

```
Environment (isolated locus — 03)
   └─ Workspace (fs + VCS scope)
        ├─ filesystem root        (the only paths a Session may touch, by default)
        ├─ repository binding      (the VCS the Workspace tracks, if any)
        └─ artifact area           (where produced outputs are collected as Evidence Candidates)
```

A Workspace answers **on what** actuation operates. Most engineering work is repository work, so a
Workspace usually *is* a repository checkout — but a Workspace need not be a repository (a scratch
directory is a valid Workspace with no VCS binding).

---

# The Workspace is the filesystem boundary

Per the Runtime security spine (`../runtime/17` §2/§4), a Session gets a **restricted working dir; no
access outside the session workspace**, default-deny. The Workspace *is* that boundary, made a
first-class object:

- Every filesystem action names a path; Actuation checks the path is **within the Workspace root**
  before enacting it (`06`). A path outside the Workspace is denied (`actuation.command_denied`),
  not clamped silently.
- Declared input artifact paths (`../runtime/17` §4) extend the readable set explicitly; nothing is
  ambient.
- The artifact area is where produced files are surfaced as Evidence Candidates by reference
  (INV-12/27) — the Workspace never embeds artifact content into events.

Making the Workspace explicit is what lets "repository write" be a *permission over a scope* (`06`)
rather than an unbounded capability.

---

# Git is a governed Workspace operation

Git operations (status, diff, add, commit, branch, merge, push) are **owned by Actuation** as
governed primitives on the Workspace's repository binding — not delegated ad hoc to each Actuator.
Centralizing them makes every runtime's git behavior uniform and uniformly governed:

| Git action | Action class (`06`) | Governance note |
|---|---|---|
| status / diff / log | `read` | always available within a Workspace with read |
| add / stage | `git-write` | requires repository-write permission |
| commit | `git-write` | requires repository-write; often an **approval gate** (`07`) — commit to a shared branch is consequential |
| branch / checkout | `git-write` | within the Workspace |
| **push** / publish | `git-publish` + `network` | outward, frequently irreversible → approval gate and network permission both required |
| merge to a protected branch | `git-write` (+ policy) | high blast radius (`../engineering/09`); gated |

Actuation **performs** these operations and **records** each as an `actuation.*` event; it never
*decides* whether a commit is warranted (that is the Execution Engine driving the Work Package) and
never *decides* whether the change is correct (Validation, INV-20). A commit is an actuation *action*
with a diff as its Evidence Candidate — not a claim of completion.

---

# Why Actuation owns filesystem and git (not each Actuator)

The Runtime docs push all provider knowledge behind the adapter (`../runtime/03` §3), which is right
for *provider mechanics*. But filesystem-within-a-scope and git-on-a-repository are **not
provider-specific** — a commit is a commit whether the runtime is Claude Code, a shell, or a remote
worker. If each Actuator re-implemented workspace and git handling, the platform would have N
inconsistent, separately-audited implementations of its most security-sensitive actions.

So Actuation provides filesystem and git as **shared, uniformly-governed primitives** that Actuators
*invoke*, keeping the Actuator thin (provider translation only) and the security surface single and
auditable. This is the core value of Actuation as a *shared substrate* rather than per-adapter code.

---

# Workspace lifecycle

```
Opened          bound to an Environment; root established; repo detected/bound
   ↓
Active          filesystem/git actions flowing (each permission-checked — 06)
   ↓
Modified        one or more mutations recorded (actuation.workspace_modified — 08)
   ↓
Preserved /     kept for reattach (10) or captured for evidence
Collected
   ↓
Released        removed on teardown if ephemeral; kept if it is a durable checkout (11)
```

Every mutation is an event (INV-13); the modified-state of a Workspace is a projection of its
`actuation.*` log, so what changed is auditable and replayable.

---

# Ownership summary

| Concern | Owner |
|---|---|
| Filesystem access within a scope | **Actuation** (governed primitive, path-checked) |
| Git operations on the Workspace repo | **Actuation** (governed primitive) |
| Which file to write / whether to commit | Execution Engine (drives the Work Package) |
| Whether a commit/push is *allowed* | Policy Engine decides; Actuation enforces (`07`, INV-28) |
| Whether the change is *correct/complete* | Validation (INV-20) |
| Provider mechanics of the runtime | the Actuator (`../runtime/03`) |

---

# North Star

A Workspace is the scoped ground a Session stands on. Filesystem and git are Actuation's shared,
governed hands on that ground — uniform across every runtime, bounded to the Workspace, checked
before every touch, and recorded after.
