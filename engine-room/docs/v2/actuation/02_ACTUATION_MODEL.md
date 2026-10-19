# Actuation Model

Status: Target Architecture (design only)

---

# Purpose

This document defines the core actuation objects — the **Actuator**, the **Actuation Command**, and
how they realize the Runtime Adapter's nine concerns — and answers the specific question:

> Should Claude Code be considered a Runtime, an Adapter, an Execution Target, or an Actuator?

---

# The four canonical actuation objects

Actuation models the external world with four objects. Three are the *nouns* (`Environment`,
`Workspace`, `Session`, each in its own document); this document defines the *verbs' owner* — the
Actuator — and the *unit of action* — the Actuation Command.

| Object | Role | Document |
|---|---|---|
| **Environment** | the isolated locus where actuation happens | `03` |
| **Workspace** | the filesystem/repository scope inside an Environment | `05` |
| **Session** | the live, long-lived, reattachable interaction | `04` |
| **Actuator** | the provider-specific driver that operates the above | this document |
| **Actuation Command** | one governed action issued into a Session | this document |

---

# The Actuator

An **Actuator** is the provider-specific driver that operates one kind of environment: a Claude Code
actuator, a shell actuator, a Docker actuator, a browser actuator, an MCP actuator, a remote-worker
actuator.

An Actuator is what **satisfies a Runtime Adapter** (`../runtime/03`). The Runtime Adapter is the
*conceptual contract* (nine concerns); the Actuator is the *concrete driver* that fulfills those
concerns **using the shared Actuation substrate** rather than bespoke private code.

The Actuator maps the adapter's nine concerns onto the actuation objects:

| Adapter concern (`../runtime/03` §2) | Actuator realizes it as |
|---|---|
| **A** advertise capabilities | register a Runtime Descriptor (Harness Registry, INV-36) declaring the environment kinds and action classes it supports |
| **B** configure | provision an **Environment** with the rendered isolation profile (`../runtime/17`) and injected secret references |
| **C** start | open a **Session** inside the Environment over a **Workspace** |
| **D** stream | surface Session output as `actuation.output` events (`08`) |
| **E** progress | translate Session progress signals to the runtime progress model (honestly *unknown* where unavailable) |
| **F** artifacts | emit produced outputs as Evidence Candidates by reference (`08`, INV-12) |
| **G** cancel / timeout / pause | suspend or terminate the Session on RM's control signal (`04`) |
| **H** terminal status | report the Session's process terminal status (never "success" — INV-20) |
| **I** clean up | tear down the Environment/Session; revoke credentials; remove ephemeral state (`11`) |

The Actuator is a **driver, never a decision-maker** — the same discipline the adapter contract
imposes (`../runtime/03` §6). It translates already-decided work into environment mechanics; it
never chooses work, runtime, verdict, or recovery.

An Actuator's provider-specific code is the *only* new provider knowledge; the objects and primitives
it operates (Environment/Workspace/Session/permissions/git/fs/terminal) are **shared and generic**,
so a new Actuator is a thin translation, not a re-implementation (`12`).

---

# The Actuation Command

An **Actuation Command** is a single governed action issued into a Session. It is the atomic unit of
actuation and the atomic unit of governance and audit.

Every command is:

- **scoped** — it belongs to one Session, one Workspace, one Environment;
- **classified** — it carries an action class (read, filesystem-write, terminal-exec, git-write,
  network, tool-call…) matched against the Permission Envelope (`06`);
- **checked before enacted** — the envelope is consulted first; a disallowed command becomes
  `actuation.command_denied` and never runs (`06`, fail-closed);
- **recorded** — an enacted command emits `actuation.command_executed` with correlation/trace
  identity (`08`, INV-39);
- **evidence-producing** — outputs (stdout, a diff, a written file, a screenshot, a tool result) are
  surfaced as Evidence Candidates by reference (INV-12/27).

Commands are issued *by the Execution Engine driving the Work Package*, not invented by Actuation.
Actuation owns *how a command is checked, enacted, and recorded* — never *which command comes next*.

---

# Is Claude Code a Runtime, Adapter, Execution Target, or Actuator?

**All of the first three describe the same thing at different layers; "Actuator" is the concrete
realization. They are not competing answers — they are four levels of one integration.**

```
Claude Code, viewed at each layer:

  Selection / capability level   →  a RUNTIME
        (a Harness of category RUNTIME; what Orchestration nominates and RM allocates — INV-37, ../runtime/00 §7)

  Integration-contract level     →  driven through a RUNTIME ADAPTER
        (the nine-concern conceptual contract — ../runtime/03)

  Realization level              →  operated by a CLAUDE CODE ACTUATOR
        (a concrete driver that opens a Session inside an Environment over a Workspace — this layer)

  Target                         →  the ENVIRONMENT + WORKSPACE it operates on
        ("execution target" is not a distinct object; the target is the Environment/Workspace)
```

Stated plainly: **Claude Code is a Runtime, fronted by a Runtime Adapter, realized by an Actuator,
operating on an Environment/Workspace.**

- It is a **Runtime** because that is how the platform *reasons about and selects* it — as a
  capability provider (INV-32/37). This is unchanged from `../runtime/`.
- It is *driven through* a **Runtime Adapter** because that is the generic contract RM uses.
- It is **realized by an Actuator** because someone has to actually launch the CLI, hold the session
  alive, enforce the workspace permissions, and record the actions — that is Actuation.
- "**Execution Target**" is not a separate canonical concept; the target of actuation is the
  Environment and its Workspace (`03`, `05`).

The same layering applies identically to Gemini CLI, Codex CLI, a shell, a container, a browser, or
an MCP server. Choosing one word ("is it a runtime *or* an actuator?") is a false choice; the honest
model is that it is a runtime *and* is realized by an actuator, at two different layers of the same
integration.

---

# Why the Actuator does not collapse into the Runtime Adapter

The Runtime Adapter is *conceptual* by explicit design (`../runtime/03` preamble: "no interface
signature, no method list, no algorithm"). The Actuator is where that concept becomes operational
mechanics. Keeping them distinct in the architecture:

- lets the **adapter contract stay frozen and abstract** (RM core reasons only about it), while the
  **Actuator evolves** with real provider mechanics;
- lets many actuators **share** the Environment/Workspace/Session/permission substrate, so security
  and audit are uniform rather than re-implemented per provider;
- gives the long-lived, reattachable **Session** (`04`) an owner distinct from the per-attempt
  **Runtime Session** — a distinction the adapter contract does not make and does not need to.

---

# North Star

An Actuator is a driver that turns a decided Work Package into governed motion inside a real
environment. Claude Code is a runtime the platform selects and an environment an actuator operates —
the same thing, seen from selection and from realization.
