# Sessions

Status: Target Architecture (design only)

---

# Purpose

This document defines the actuation **Session** — the live, stateful, **long-lived and reattachable**
interaction with an Actuator — and how long-running work (Claude Code running for hours, a shell
mid-execution, a Docker container still alive, a browser paused) is represented.

It also fixes the relationship between the actuation Session and the Runtime Manager's per-attempt
**Runtime Session**, which are different objects.

---

# What a Session is

An actuation **Session** is the live interaction between an Actuator and an Environment, over a
Workspace, for a stretch of real work. A Claude Code CLI running for two hours is one Session; a
shell executing a long build is one Session; a browser automation paused mid-flow is one Session; an
open MCP connection is one Session.

A Session has a **kind** (`cli`, `terminal`, `ide`, `browser`, `mcp`, `process`) and belongs to
exactly one Environment (`03`) and, while doing filesystem/git work, operates on one Workspace
(`05`).

Its state is a **projection of the `actuation.*` event log** (INV-13/14) — never hidden mutable
truth. Restoring the projection from the log (optionally a snapshot plus tail replay) reconstructs
the Session exactly (INV-14/18).

---

# The distinction that matters: Session vs Runtime Session

The Runtime layer defines a **Runtime Session** that is explicitly *one attempt* and *not durable
beyond its attempt* (`../runtime/02` §1, §9). That is correct for a *binding* — it binds one
Execution Package to one allocated runtime for one attempt.

But a *live external environment* is not one attempt. A Claude Code process can survive a Nexus
retry; a container keeps running; a browser stays paused. Modeling that requires an object the
one-attempt binding cannot provide. The actuation **Session** is that object.

```
Runtime Session (RM-owned)          Actuation Session (Actuation-owned)
--------------------------          ----------------------------------
binds package ↔ allocated runtime   the live interaction with the environment
one attempt (attempt ordinal)       may span multiple attempts (reattach)
not durable beyond the attempt      long-lived; persists across attempts until torn down
a binding + lifecycle               a real process / connection / container
../runtime/02                       this document
```

**Relationship:** a Runtime Session is *realized by attaching to* an actuation Session. Attempt *n*
opens (or reattaches to) a Session; if attempt *n* fails and Recovery chooses **reattach** (`10`),
attempt *n+1* — a new Runtime Session — binds to the **same** live actuation Session rather than
recreating the environment. This decoupling is the entire reason to model the Session separately: it
enables reattach/resume of live environments, which the per-attempt binding cannot express.

> This does not modify `../runtime/02`. The Runtime Session stays exactly as specified (one attempt,
> non-durable). Actuation adds a *lower*, longer-lived object beneath it, referenced by the runtime
> layer's `runtime_ref`/adapter — additive, not a change.

---

# Session lifecycle

```
Opening          Actuator launches or attaches the interaction (03 launch/attach)
   ↓
Live             actively driven by the Execution Engine; commands flowing (02)
   ↓
Idle             open but no command in flight (e.g. Claude Code awaiting input)
   ↓
Suspended /      detached but ALIVE — the process/container/connection persists,
Detached         no Runtime Session currently bound (long-running work parked)
   ↓
Reattaching      a new attempt binds back to the live Session (10)
   ↓
Terminating      graceful stop, then forced (../runtime/03 concern G)
   ↓
Terminated       the interaction ended; Environment may be destroyed or kept (03)
```

Failure path: any state → **Failed** (typed error, `09`) → teardown (`11`).

---

# How long-running situations are represented

The exercise named four; each is a Session state, not a special case:

| Situation | Representation |
|---|---|
| **Claude Code running for hours** | a `cli` Session in state `Live`/`Idle`; long duration is normal, not a timeout unless Strategy says so (`../runtime/10`) |
| **Shell still executing** | a `terminal` Session in state `Live`; the process is running; output streams as `actuation.output` |
| **Docker container still alive** | a `process`/`cli` Session whose Environment is a container in `Active`; if no Runtime Session is bound, the Session is `Detached` and the container is kept alive |
| **Browser automation paused** | a `browser` Session in state `Suspended`; the driver/profile persists; resumable by reattach |

The unifying idea: **a live environment does not require an active attempt.** A Session can be
`Detached`/`Suspended` — alive but unbound — and later reattached. This is what makes "still alive"
and "paused for hours" first-class rather than an edge case.

---

# Checkpoints and Sessions

Sessions are checkpoint-aware (INV-18). A checkpoint is a referenced, point-in-time capture
associated with a Session (partial artifacts, resumable state), recorded as data and referenced by
id — never embedded (`../runtime/02` §7). Actuation is the *mechanism* that associates and, on
direction, resumes from a checkpoint; **Recovery/Strategy decide whether and when** (`10`). Whether a
given Session kind can genuinely resume (vs only restart) is an Actuator-declared capability
(`../runtime/20` G-4): a stateless `terminal` may only restart; a container or CLI may resume.

---

# Ownership and lifetime

- **Owner:** the Actuation Layer owns the Session for its entire life, including while the Execution
  Engine drives work within it.
- **Created when:** an Actuator opens or attaches an interaction for a Runtime Session.
- **Kept when:** work is long-running or parked — the Session may be `Detached` yet alive.
- **Destroyed when:** Recovery/Orchestration directs termination, the work concludes and no reattach
  is expected, or teardown is forced (`11`). Its event record is permanent in the log.

---

# What a Session is not

- Not the Runtime Session (it *realizes* one, or several across attempts).
- Not the Environment (it *lives inside* one).
- Not the Work Package (it *carries out* interactions for one).
- Not a verdict of success (Validation decides, from Evidence — INV-20).

---

# North Star

A Session is the live pulse of real work — a running CLI, an executing shell, a waiting browser.
Nexus models it as a first-class, long-lived, reattachable object so that "still running" and
"paused for hours" are ordinary states, and a retry can rejoin live work instead of throwing it away.
