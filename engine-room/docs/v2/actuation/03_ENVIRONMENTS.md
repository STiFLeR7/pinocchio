# Environments

Status: Target Architecture (design only)

---

# Purpose

This document defines the **Environment** — the canonical concept for the isolated locus where
actuation happens — and how Nexus launches, attaches to, and destroys one without coupling to any
provider.

---

# What an Environment is

An **Environment** is the isolated place an Actuator operates within: a local machine context, a
Docker container, a remote host, a Kubernetes pod, a browser profile host. It is the boundary that
carries the **isolation surface** (`../runtime/17` §2) — the sandbox, filesystem scope, network
posture, and credential mechanism within which every action for a Session occurs.

An Environment answers **where** actuation physically takes place. It is provider-independent as a
*concept*; its concrete boundary is rendered by the Actuator for that kind (`../runtime/17` §2).

```
Environment (isolated locus)
   ├─ isolation surface       (sandbox / fs scope / network posture — ../runtime/17)
   ├─ Workspace(s)            (filesystem/repository scope — 05)
   └─ Session(s)              (live interactions — 04)
```

---

# Canonical mapping of "physical" concepts

The exercise asked how Nexus should represent repositories, workspaces, terminals, CLI sessions, IDE
instances, and remote machines. The canonical answer collapses them onto four objects:

| Physical concept | Canonical object |
|---|---|
| remote machine, container, pod, local host | **Environment** |
| repository, checkout, working directory | **Workspace** (`05`) |
| terminal | **Session** of kind `terminal` (`04`) |
| CLI session (Claude Code, Gemini, Codex) | **Session** of kind `cli` |
| IDE instance (VS Code, JetBrains) | **Session** of kind `ide` (hosted in an Environment) |
| browser | **Session** of kind `browser` |
| MCP connection | **Session** of kind `mcp` |

There is no separate "terminal object" or "IDE object": those are **Session kinds** operating inside
an Environment over a Workspace. This keeps the model small — four nouns absorb every environment
Nexus will meet (`12`).

---

# Environment lifecycle

An Environment's state is a projection of the `actuation.*` event log (INV-13/14), never a mutable
field bag.

```
Requested        an Actuator needs an Environment for a Session
   ↓
Provisioning     render the isolation profile; acquire the locus
   ↓
Ready            isolation established; Workspace(s) can be opened
   ↓
Active           one or more Sessions live inside it
   ↓
Detached         no live Session, but the Environment persists (long-lived — 04, 10)
   ↓
Destroying       teardown: revoke credentials, remove ephemeral state (11)
   ↓
Destroyed        gone; only its event record remains (permanent in the log)
```

Failure path: any state → **Failed** (typed error, `09`), which routes to teardown (a failed
Environment is still torn down; nothing is left live — `11`).

---

# Launch, attach, resume, detect failure, terminate — without provider coupling

The exercise asked how these five operations work without coupling to providers. Each is an
Environment/Session lifecycle verb the Actuator translates; the *verb set* is generic, the
*mechanics* are the Actuator's.

| Operation | Generic meaning | Actuator translates to (examples) |
|---|---|---|
| **launch** | provision a fresh Environment + open a Session | spawn a process; `docker create/start`; open a browser; SSH to a host; connect to MCP |
| **attach** | bind a new Runtime Session attempt to an **already-live** Environment/Session | reconnect to a running CLI; re-open a container's exec stream; reconnect an MCP session |
| **resume** | continue from a recovery checkpoint in a capable Environment | restore from a checkpoint the Actuator declared it supports (`../runtime/20` G-4) |
| **detect failure** | observe a terminal/aberrant condition and emit a typed failure | process exit code; container OOM; broken connection; timeout (`09`) |
| **terminate** | end the Session and (if owned) destroy the Environment | kill the process group; `docker stop/kill`; close the driver; disconnect |

Because the verb set is fixed and provider-independent, RM core and Recovery reason in these terms
(INV-32); only the Actuator knows the provider mechanics. A future environment kind supplies its own
translation for the same verbs and joins without redesign (`12`).

---

# Ownership of the Environment

- The **Actuation Layer owns** the Environment's lifecycle and its isolation enforcement.
- **RM does not own it.** RM owns the per-attempt Runtime Session (the binding); Actuation owns the
  *place* that binding runs in. This separation is precisely what lets an Environment **outlive a
  single attempt** and be **reattached** by a later attempt (`04`, `10`) — a capability the
  one-attempt Runtime Session model deliberately excludes (`../runtime/02` §9).
- The **Harness Registry owns availability/health** of an Environment kind's provider (INV-36);
  Actuation reads it, never re-owns it.

---

# Isolation is the Environment's defining property

An Environment is not merely a location; it is a **jail with walls** (`../runtime/17` §9). It carries
its category's isolation profile, and a category that cannot establish its required isolation is
**refused, not run with weaker walls** (fail-closed, `../runtime/17` §5, `11`). The Environment is
therefore the object on which blast radius (`09`, `11`) is bounded: everything a Session does is
contained within its Environment's declared surface.

---

# North Star

An Environment is the walled place where work happens. Nexus launches, attaches to, resumes, and
tears down environments through one provider-independent verb set — and never lets an action escape
the walls the Environment declared.
