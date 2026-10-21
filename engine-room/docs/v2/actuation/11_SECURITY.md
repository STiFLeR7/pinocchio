# Security

Status: Target Architecture (design only)

---

# Purpose

This document defines the actuation security model: **secret handling, least privilege, redaction,
blast-radius containment, and teardown** — at the granularity of individual actions inside a real
environment. It **honors, and never weakens**, the Runtime security spine (`../runtime/17`); it
extends it from session-allocation granularity to per-action granularity.

---

# The security spine (inherited, non-negotiable)

The four rules of `../runtime/17` §1 are binding here verbatim:

1. **`.env` is the single source of truth for secrets.** Secret *values* live only in `.env`. They
   are never printed, and never embedded in an event payload, log line, stream chunk, artifact, or
   Work Package.
2. **Secrets reach an environment by injected *reference*, through the Actuator, at configure-time**
   — never baked into the immutable package.
3. **Least privilege.** A Session receives only the action classes, credentials, filesystem scope,
   and network reach its package declared — nothing more (`06`).
4. **Fail-closed.** A missing/unresolved credential, or a failed isolation setup, **refuses the
   Session** (→ `Failed`, `09`). There is no degraded-but-acting state.

Actuation is the layer that finally touches the real world, so it is the layer where these rules
must bite hardest.

---

# Actuation does not own secrets

Ownership is explicit and unchanged from the standing platform rule:

- Actuation **consumes injected secret references** (handles, env-var names, scoped tokens) resolved
  from `.env` at configure-time (`../runtime/17` §3). It **never stores secret values**, never
  persists them, never prints them, and never places them in an `actuation.*` payload (`08`).
- Environment variables are **managed** by Actuation (it injects the reference into the Environment),
  but the secret **value** is owned by `.env` and handed to the Actuator only at configure.
- A future **Secrets Broker** (a named seam, `13`) may mediate resolution; Actuation still only ever
  holds references. This directly honors the operator's standing constraint: `.env` is the single
  source, values are never printed, no second credential store is created.

```
.env (values ONLY here)
   │ resolve → injected REFERENCE (handle, not value)
   ▼
Actuator.configure  (Environment provisioning — 03)   ← value present only at runtime, scoped
   ▼
Session actions  (value usable, never logged/embedded — redacted at edges below)
   ▼
Teardown  → credential handle REVOKED, env scrubbed, ephemeral state removed
```

---

# Redaction at the action edges

Secrets must not escape through the channels Actuation operates (`../runtime/17` §6), applied at
per-action granularity:

- **`actuation.output` (streams).** stdout/stderr/structured lines are redacted **at capture**, so a
  secret a runtime process echoes is masked before it becomes an event payload.
- **Evidence Candidates (artifacts).** Referenced by id; redaction policy ensures a secret value
  cannot land in an artifact's content or metadata (INV-12/27). A committed diff, a written file, a
  screenshot are all subject to redaction at the edge.
- **Events & failures.** No secret value ever enters an `actuation.*` payload (`08`) or an
  `actuation.failed` class (`09`) in the first place; redaction at the stream/artifact edge defends
  against values a *runtime itself* emits.

> Non-embedding protects against Actuation leaking a secret it injected; redaction protects against
> the runtime leaking a secret it was given. Both are required (`../runtime/17` §6).

---

# Least privilege, per action

The Permission Envelope (`06`) is the least-privilege mechanism, enforced **before every action**:

- Privilege is **opt-in by declaration, never ambient** — an undeclared action class is absent, not
  merely unused (`../runtime/17` §4).
- A package that declares nothing gets read of its Workspace and nothing else.
- Path containment (Workspace, `05`) and endpoint containment (declared network) are enforced per
  action — a write outside the Workspace or egress to an undeclared endpoint is denied (`06`).
- Each retry re-derives its own minimal envelope; a reattached Session inherits no wider privilege
  than the new attempt is granted (`06`, `10`).

---

# Blast-radius containment

Actuation is where **blast radius** (`../engineering/09`) becomes physically bounded:

- Every action occurs **inside an Environment's isolation surface** (`03`, `../runtime/17` §2) — a
  restricted process, a namespaced container, an ephemeral browser profile, a scoped provider
  session, an mTLS-trusted remote channel. An action cannot reach outside the walls the Environment
  declared.
- **Consequential/irreversible actions are gated** (`07`) — commit-to-shared, push, deploy,
  destructive deletes, outbound external messages pause for approval before they occur.
- An Environment that **cannot** establish its required isolation is **refused**, not run with weaker
  walls (fail-closed, §spine.4). Selection and policy filter on declared isolation before allocation
  (`../runtime/17` §2).

The combination — walls + per-action permission + approval gates on the irreversible — is the
actuation expression of "safe autonomy": the platform can act, but only within a contained, gated,
recorded envelope.

---

# Teardown is a security boundary

Security ends at `Destroyed`, not at `Completed` (`../runtime/17` §7):

- On **every** terminal path (completed / cancelled / failed), teardown runs: credential handles
  revoked, injected env scrubbed, ephemeral profiles/workspaces removed, containers torn down,
  processes killed.
- A **kept-alive `Detached` Session** for reattach (`04`, `10`) is the *only* non-torn-down state,
  and it is bounded (a lapsed reattach window triggers teardown), governed, and recorded — a walled,
  auditable pause, not a leak.
- A teardown that fails to revoke or clean is a **surfaced typed anomaly** (`09`), never swallowed;
  the allocation is still released so capacity does not leak.

---

# Invariants & rules this document honors

| Rule | How honored |
|---|---|
| `.env` single source; secrets never printed/embedded | references only; redaction at edges; no value in any payload |
| least privilege (platform rule) | envelope derived from declarations; default-deny per action (`06`) |
| fail-closed (INV-30) | missing credential / unbuildable isolation refuses the Session |
| INV-12 / INV-27 evidence by reference | artifacts referenced; redaction prevents secret content |
| INV-32 provider-independent capabilities | action classes abstract; provider mapping at the Actuator |
| dependency direction (`00`) | provider/isolation specifics live only in Actuators; substrate stays generic |

---

# North Star

Actuation holds the platform's most dangerous power — real hands on real repositories, terminals, and
networks — and wraps it in walls, keys it to a least-privilege envelope, gates the irreversible,
redacts every secret at every edge, and revokes everything at teardown. Power, fully contained.
