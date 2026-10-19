# Extensibility

Status: Target Architecture (design only)

---

# Purpose

This document shows how new actuators — Claude Code, Gemini CLI, Codex CLI, VS Code, JetBrains,
GitHub Actions, remote Linux, Kubernetes, MCP — integrate **without redesign**, and why the
architecture absorbs environments that do not exist today.

---

# The absorption property

The set of actuators is **open** precisely because the actuation model is **closed**. A new
environment kind joins by supplying an **Actuator** that:

1. registers a Runtime Descriptor into the Harness Registry (INV-36), advertising the environment
   kinds and action classes it supports (provider-independent capabilities, INV-32);
2. translates provider mechanics onto the **existing** objects and verbs — `Environment`,
   `Workspace`, `Session`, `Actuation Command`, and the launch/attach/resume/detect/terminate verb
   set (`03`);
3. emits only the canonical `actuation.*` events (`08`) and produces artifacts as Evidence Candidates
   by reference (INV-12);
4. declares its isolation profile and honors the Permission Envelope on every action (`06`, `11`).

Nothing upstream changes — not RM core, not the Runtime Adapter contract, not the Execution Engine,
not Validation, not Recovery, not any ADR or invariant. Adding an actuator is "a directory of
adapter code plus a Registry registration" (`../runtime/03` §5), now built on the shared Actuation
substrate rather than from scratch.

---

# The same model, many actuators

Every named actuator maps onto the identical objects. The columns are provider mechanics; the rows
show the model is constant.

| Actuator | Environment | Session kind | Workspace | Notable action classes |
|---|---|---|---|---|
| **Claude Code** | local / container | `cli` | repo checkout | read, repository-write, git-write, terminal-exec |
| **Gemini CLI** | local / container | `cli` | repo checkout | read, repository-write, terminal-exec |
| **Codex CLI** | local / container | `cli` | repo checkout | read, repository-write, git-write |
| **Shell** | local / container | `terminal` | working dir | terminal-exec, filesystem-write |
| **VS Code** | local / remote | `ide` | folder/workspace | read, filesystem-write, terminal-exec (integrated terminal) |
| **JetBrains** | local / remote | `ide` | project | read, filesystem-write, terminal-exec |
| **GitHub Actions** | remote runner | `process` (dispatched) | checkout on runner | terminal-exec, git-publish, network |
| **Remote Linux** | remote host | `terminal`/`process` | remote workspace | terminal-exec, filesystem-write, network |
| **Kubernetes** | pod | `process` | mounted volume | terminal-exec (exec into pod), network |
| **MCP server** | server session | `mcp` | server-declared scope | tool-call/mcp, network (declared tools only) |

Read by row to see one actuator; read by column to see the *object* is identical everywhere — only
the translation differs. That invariance is the point of the substrate.

---

# Where a new actuator's pressure is absorbed

| Pressure from a new actuator | Absorbed in | Unchanged |
|---|---|---|
| a novel launch/attach mechanism | the Actuator's translation for the verb set (`03`) | Environment/Session lifecycle (`03`/`04`) |
| an exotic session shape (e.g. a GPU job, a WASM sandbox) | a new `Session` kind mapped onto the state machine (`04`) | the Session states and `actuation.*` events (`08`) |
| a new artifact kind | mapping to Evidence Candidate by reference (`08`, INV-12) | the artifact/event model |
| a different isolation surface | the Actuator's declared isolation profile (`11`, `../runtime/17`) | the least-privilege/permission model (`06`) |
| a new action it can perform | a new abstract action class advertised in its descriptor (INV-32) | the envelope-enforcement mechanism (`06`) |
| a genuine resume capability | an Actuator-declared resume capability (`../runtime/20` G-4) | the recovery mechanisms (`10`) |

---

# Guarantees that make this safe

- **No provider-specific assumptions in the substrate.** Actuation core reasons only in
  Environment/Workspace/Session/Command/permission/event terms; it never branches on a provider. If
  such a branch appears in the substrate, the architecture has been violated (mirror of
  `../runtime/03` §3).
- **Capabilities, not providers, are matched.** A new actuator advertising a known capability is
  usable the moment it registers (INV-32); no special-casing.
- **Events and states are fixed.** A new actuator maps onto the canonical `actuation.*` events (`08`)
  and Session/Environment states (`03`/`04`); it coins none of its own.
- **Honest degradation.** Where an actuator cannot express something (true progress, genuine resume),
  it reports the honest model value (*unknown*/*unsupported*) rather than fabricating — so the rest
  of the platform reasons over truthful facts (`../runtime/03` §5).
- **Uniform governance.** A new actuator inherits the Permission Envelope (`06`), approval gates
  (`07`), and security spine (`11`) for free — it does not re-implement (or accidentally weaken)
  them.

---

# Human as an actuator?

The Harness model already lists "Human Operator" as a Runtime (`../11_HARNESS.md`). A human actuator
fits the same model: an Environment (the human's workspace), a Session (a task assignment), Evidence
Candidates (their produced artifacts), and approval-style interaction — governed and recorded like
any other. This is a named extension (`13`), not a redesign: the model already has the shape.

---

# North Star

The set of environments Nexus can operate is open because the way it operates them is closed. A new
CLI, IDE, CI runner, cluster, or protocol joins by translating its mechanics onto the same
environment, workspace, session, permission, and event vocabulary — and inherits the platform's
governance and security without asking for an exception.
