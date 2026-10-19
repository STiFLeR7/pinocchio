# Permissions

Status: Target Architecture (design only)

---

# Purpose

This document defines the **Permission Envelope** — the scoped set of action classes a Session may
perform — and the rule that Actuation is the **enforcement point** for it while the Policy Engine
remains the **decision point** (INV-28).

---

# The posture, stated first

> Actuation is an **enforcement point**, never a **decision point**. It reads the resolved permission
> envelope (derived from the package's declared requirements and the Policy bundle the Harness
> resolved), and it enforces that envelope on **every action, before the action happens**. It never
> evaluates policy, never widens the envelope, and — when a required grant is absent — it **denies**
> (fail-closed, INV-30).

This is the same posture the Runtime Manager holds for governance (`../runtime/18` §1), applied one
level finer: RM enforces at *session allocation*; Actuation enforces at *each action*.

---

# The action classes

Permissions are expressed as **provider-independent action classes** (INV-32), matching the
exercise's examples and the Runtime least-privilege dimensions (`../runtime/17` §4):

| Action class | Grants | Default (undeclared) |
|---|---|---|
| **read** | read within the Workspace + declared input paths | read of Workspace only |
| **repository-write** (`git-write`, filesystem-write) | mutate files / stage / commit within the Workspace | **denied** |
| **terminal-exec** | run commands in a `terminal` Session | **denied** |
| **network** | egress to declared endpoints | **deny egress** |
| **git-publish** | push / publish outward | **denied** (also needs `network`) |
| **docker** | create/operate containers | **denied** |
| **browser** | drive a browser Session | **denied** |
| **tool-call / mcp** | invoke declared MCP tools | **denied** unless declared |

Privilege is **opt-in by declaration, never ambient** (`../runtime/17` §4): a package that declares
nothing gets the most restricted viable envelope — read of its Workspace and nothing else.

---

# The Permission Envelope

A **Permission Envelope** is the concrete set of granted action classes (and their scopes) for one
Session. It is:

- **derived, not invented** — from the package's declared capability/credential/filesystem/network
  requirements (`../runtime/17` §4) intersected with the resolved Policy bundle (`../runtime/18` §3);
- **least-privilege** — the *minimum* the declared work needs (INV-32 expressed abstractly, mapped
  to the concrete Environment at bind);
- **per-Session** — each Session (and each retry, `../runtime/02` §6) provisions its own envelope;
- **immutable for the Session's life** — widening requires a new governed decision, not a mutation.

```
Declared requirements (package)  ┐
                                 ├─► Policy Engine evaluates ─► resolved Policy bundle
Policy (data, ADR-004)           ┘                                     │
                                                                       ▼
                                              Permission Envelope (least-privilege, per Session)
                                                                       │
                                            enforced per action ◄──────┘   (this layer)
```

---

# Per-action enforcement

Every Actuation Command (`02`) is checked against the envelope **before** it is enacted:

```
Command issued (Execution Engine drives it)
   │
   ▼
Classify action (read / repository-write / terminal-exec / network / git-publish / …)
   │
   ▼
In envelope?  ── no ──►  actuation.command_denied   (typed, recorded — 08; NO action taken)
   │ yes
   ▼
Enact  ──►  actuation.command_executed  (recorded, correlated — 08)
```

- A denied command **does not run** and is **not silent**: it is a recorded `actuation.command_denied`
  event carrying the class denied and the envelope reference (`08`), auditable like any other action
  (INV-31). Silent clamping is forbidden — denial is explicit.
- Path checks (Workspace containment, `05`) and endpoint checks (declared network, `../runtime/17`
  §4) are part of classification: a write outside the Workspace or egress to an undeclared endpoint
  is a class the envelope does not grant → denied.

---

# Permissions and approval are different gates

Two distinct controls, often confused:

| Gate | Question | Owner | Mechanism |
|---|---|---|---|
| **Permission** | *May this class of action ever occur for this Session?* | Policy Engine decides; Actuation enforces | envelope check, per action (this doc) |
| **Approval** | *Should this specific consequential action proceed now?* | the approver decides; Actuation pauses | approval gate (`07`) |

A commit may be *permitted* (repository-write in the envelope) yet still require a human *approval*
before it proceeds (a consequential/irreversible action, per Engineering Intelligence's autonomy
gates — `../engineering/08`). Permission bounds *what is possible*; approval controls *whether a
possible action happens now*. Both must pass.

---

# Least privilege is derived, and fails closed

- The envelope grants **only** what the package declared; anything undeclared is **absent, not merely
  unused** (`../runtime/17` §4). 
- If a required grant cannot be established (a credential is missing, an isolation surface can't be
  built), the **Session is refused** before any action — the same fail-closed rule as runtime
  security (`../runtime/17` §5). There is no degraded-but-acting state.
- A retry re-derives its own least-privilege envelope; reattaching to a live Session (`10`) does not
  inherit a wider envelope than the new attempt is granted.

---

# North Star

Actuation carries a key ring it did not cut. The Policy Engine decides which doors exist; Actuation
opens only those, one door at a time, checking before every push and recording every attempt —
including the ones it refuses.
