# Event Model

Status: Target Architecture (design only)

---

# Purpose

This document defines the canonical **`actuation.*`** event taxonomy — the append-only facts that are
the single source of truth for everything actuation does — and how it relates to the existing
`runtime.*` events without duplicating them.

---

# Events are the source of truth

Per ADR-001 / INV-13, the append-only event log is authoritative; a Session's, Environment's, or
Workspace's "current state" is a **projection** of the `actuation.*` log (INV-14), idempotent
(INV-16) and deterministic on replay (INV-17: timestamps and any non-deterministic values live only
in payloads). Every cross-boundary fact carries correlation and trace identity (INV-39).

Actuation events are **raw Execution Events**: Actuation emits facts; only **Supervision** turns them
into Observations (INV-11). Artifacts referenced by events are **Evidence Candidates**; only
**Validation** promotes them to Evidence (INV-12).

---

# `actuation.*` vs `runtime.*` — different granularity, no overlap

The Runtime layer already defines `runtime.*` events for **session-lifecycle** facts (prepared,
allocated, waiting_approval, completed, released, destroyed — `../runtime/15`). Actuation does **not**
duplicate these. `actuation.*` events model a **finer granularity**: the individual governed
**actions inside the environment** that `runtime.*` never described.

```
runtime.*     : "a Runtime Session was allocated / prepared / completed / destroyed"   (session lifecycle)
actuation.*   : "a command was executed / a file was written / a commit was made /      (action lifecycle)
                 a permission was denied / an environment was created"
```

A `runtime.completed` says the attempt's process ended. The `actuation.*` stream says *what the
process did* — every command, mutation, and artifact — the layer of fact that makes real actuation
auditable.

---

# The canonical taxonomy

Grouped by object. This set is **complete and closed** for actuation's defined scope; a new Actuator
maps its provider reality onto these events and coins none of its own (`12`, mirroring
`../runtime/03` §5).

## Environment (`03`)

| Event | Fact |
|---|---|
| `actuation.environment_created` | an Environment was provisioned (isolation profile rendered, **no secrets** in payload — `11`) |
| `actuation.environment_detached` | the Environment persists with no live-bound Session |
| `actuation.environment_destroyed` | teardown complete; credentials revoked, ephemeral state removed |

## Session (`04`)

| Event | Fact |
|---|---|
| `actuation.session_started` | a Session was opened |
| `actuation.session_attached` | a Runtime Session attempt attached to a (possibly pre-existing live) Session |
| `actuation.session_suspended` | the Session detached but remains alive (long-running/paused) |
| `actuation.session_resumed` | a suspended/detached Session was resumed (causation → the suspend/checkpoint) |
| `actuation.session_terminated` | the Session ended (normal / cancelled / killed) |

## Command / interaction (`02`, `06`)

| Event | Fact |
|---|---|
| `actuation.command_issued` | a command entered the envelope check |
| `actuation.command_executed` | a permitted command was enacted (with its Evidence Candidate refs) |
| `actuation.command_denied` | a command was refused by the Permission Envelope (class + envelope ref) — no action taken |
| `actuation.output` | a stream chunk (stdout/stderr/structured), **redacted** at capture (`11`) |

## Workspace (`05`)

| Event | Fact |
|---|---|
| `actuation.workspace_opened` | a Workspace was bound to an Environment |
| `actuation.workspace_modified` | a filesystem/git mutation occurred (path/diff **referenced**, not embedded — INV-27) |
| `actuation.workspace_released` | the Workspace was released/collected at teardown |

## Artifact (`08` → Validation)

| Event | Fact |
|---|---|
| `actuation.artifact_generated` | a produced output was surfaced as an **Evidence Candidate** by reference (INV-12) |

## Governance (`07`)

| Event | Fact |
|---|---|
| `actuation.approval_requested` | a gated action paused for approval (taxonomy + approval_ref) |
| `actuation.approval_resolved` | the approval was granted/rejected (causation → the request) |

## Failure (`09`)

| Event | Fact |
|---|---|
| `actuation.failed` | a typed failure occurred (class + owner; **never a secret value** — `11`) |

`actuation.started` (the exercise's example) is expressed as the pair `environment_created` +
`session_started`, so "actuation began" is reconstructable without a redundant umbrella event.

---

# Event discipline

- **Never embed content.** Diffs, files, command output, screenshots are referenced by id; the event
  carries the reference, never the bytes (INV-27, ADR-003). Secret values never enter any payload
  (`11`, `../runtime/17` §3).
- **Redact at the edge.** `actuation.output` is redacted at capture so a secret a runtime echoes is
  masked before it becomes a payload (`../runtime/17` §6).
- **Correlate everything.** Every event carries the operation-wide `correlation_identifier` and
  causation links (e.g. `session_resumed` → the `session_suspended`/checkpoint; `approval_resolved` →
  `approval_requested`), so *what happened and why* is one causal stream (INV-39).
- **Deterministic ids.** Event ids derive from stable identities (Session id + kind tag + monotonic
  sequence), so the stream is ordered and dedup-keyed (INV-16), and replay yields identical state
  (mirrors `../runtime/02` §3).

---

# What consumers do with the stream

| Consumer | Uses `actuation.*` for |
|---|---|
| **Supervision** | derive Observations, health, progress (INV-11/23) |
| **Validation** | collect Evidence Candidates → Evidence → completion verdict (INV-12/20) |
| **Recovery** | see failure class + last checkpoint to decide continuation (INV-22, `10`) |
| **Operator Experience** | timeline/explorer read-only projections (`../runtime/operator`) |
| **Audit/Governance** | the immutable trail of every permitted and denied action (`07`, INV-31) |

None writes back into Actuation state; the log is one-way (INV-16).

---

# North Star

If it is not in the `actuation.*` log, it did not happen. Every environment created, every command
run or refused, every file changed, every artifact produced is a correlated, immutable, content-free
fact — the ground truth beneath all supervision, validation, recovery, and audit.
