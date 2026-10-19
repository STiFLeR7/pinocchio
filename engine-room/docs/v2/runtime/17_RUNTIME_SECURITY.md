# 17 — Runtime Security

**Status:** design only. Defines the Runtime Manager's (RM) security model: **sandbox
boundaries, filesystem access, credential handling, environment isolation, secret
propagation, and least privilege — per runtime category**. RM **prepares and
supervises**; it never performs work and never weakens these boundaries. Every runtime
category carries its **own isolation profile**; there is no single shared sandbox.
These rules are platform-wide and binding — they are honored, not invented, here.

---

## 1. Security spine (non-negotiable)

Four rules govern everything below. They are stated once and never contradicted:

1. **`.env` is the single source of truth for secrets.** Secret *values* live only in
   `.env`. They are never printed, and never embedded in an Execution Package, a
   `runtime.*` event payload, a log line, a stream chunk, or an artifact.
2. **Secrets reach a runtime by injected reference, through the adapter
   (`03_RUNTIME_ADAPTERS.md`), at configure-time** — never by being baked into the
   immutable package (`01` §3 boundary; `package_builder` carries no secret field).
3. **Least privilege.** A session receives only the capabilities, credentials,
   filesystem scope, and network reach its package's declared requirements demand —
   nothing more.
4. **Fail-closed.** A missing/unresolved credential, or a failed isolation setup,
   **refuses the session** (transition to `Failed`, `11`). There is no
   degraded-but-running state. (An A-001-style auth check fails closed: absence of a
   positive grant is denial.)

> RM changes *where* and *how* already-decided work is hosted. Security is the boundary
> of that hosting: a runtime gets exactly the world its package declared, and not one
> capability, path, or secret more.

## 2. Isolation profiles per runtime category

Each runtime category has its **own** isolation profile, rendered at the
`Created → Prepared` configuration step (`07` §1, `01` §4 step 10) and torn down at
`Destroyed` (`07` §6). RM's core stays generic; the concrete boundary is enforced by
the adapter for that category (`03`, `19`).

| Runtime category | Sandbox boundary | Filesystem scope | Credential mechanism | Network posture |
|---|---|---|---|---|
| **Shell** | OS process + restricted env | restricted working dir; no access outside the session workspace | env-var references injected by adapter; revoked at teardown | inherited-but-policy-bounded; default deny egress unless package declares it |
| **Python** | OS process + restricted env/interpreter | restricted working dir; declared input artifact paths only | env-var / handle references via adapter | default deny egress unless declared |
| **Docker** | container + namespaces (pid/mount/net/user) | container-internal FS; only declared mounts bound in | secrets injected as env/mounted refs into the container at start; never in the image | per-container network policy; default isolated, declared ports only |
| **Browser** | sandboxed driver + ephemeral profile | ephemeral profile dir; downloads to session workspace only | scoped session token / profile credential via adapter; profile destroyed at teardown | controlled origin/allowlist; no ambient host network |
| **Claude Code / Gemini CLI** | provider session boundary | provider-scoped workspace; host FS only via declared bridge | scoped provider token (handle), least-scope; never the raw key | provider endpoint only |
| **MCP server** | provider/server session boundary | server-declared resource scope | scoped server token / handle via adapter | server endpoint only; declared tools only |
| **Remote worker** | network boundary + mTLS-style mutual trust | remote-side workspace; no local FS | short-lived scoped credential over the trusted channel | authenticated channel only; no other peers |
| **Unknown future runtime** | declares its own profile at registration (`04`/`19`) | declared scope or refuse | adapter-declared mechanism or refuse | declared posture or default deny |

Notes:

- The profile is **rendered into config, never into the package** — `runtime.prepared`
  records the isolation profile *with no secrets* (`15`).
- A runtime that **cannot** satisfy its required isolation profile is **refused**
  (fail-closed, §1.4), not run with a weaker boundary. Selection (`06`) and policy
  (`18`) filter on declared isolation before allocation.
- "Default deny" is the posture for filesystem and network: a capability the package
  did not declare is absent, not merely unused (§4).

## 3. Secret propagation (the full path)

```
   .env  (single source of truth — values live ONLY here)
     │  resolve to an injected REFERENCE (a handle, not a value)
     ▼
   Adapter.configure  (Created → Prepared, step 10)   ← values enter here, by reference
     │
     ▼
   Runtime process / container / session  (values present only at runtime, scoped)
     │
     ▼
   Teardown (→ Destroyed, 07 §6)  ── credential handle REVOKED, env scrubbed, profile removed
```

- **Source:** `.env` only. Resolution turns a declared requirement into an **injected
  reference** (an env-var name, a mounted handle, a scoped token) — the **value** is
  handed to the adapter at `configure`, and to nothing else.
- **Never embedded:** not in the Execution Package (it is immutable and content-free of
  secrets — `package_builder` has no secret field), not in any `runtime.*` event
  payload, not in logs, not in stream chunks (`08`), not in artifacts (`13`).
  `runtime.prepared` deliberately carries the isolation profile **without** secrets
  (`15`).
- **Never printed:** secret values are treated as sensitive end-to-end; no code path,
  diagnostic, or error detail (`11`) prints a value.
- **Revoked at teardown:** at `Destroyed`, adapter cleanup revokes credential handles,
  scrubs the injected environment, and removes ephemeral profiles/temp workspaces
  (`07` §6 ties credential revocation to teardown). A failed revocation is recorded as
  a **typed teardown error** (`11`) and surfaced — never hidden — but the session still
  reaches `Destroyed` (no leaked-and-silent path).

## 4. Least privilege (derived from declared requirements)

Each session is provisioned **only** what its package declared:

| Provisioned dimension | Derived from | Default when undeclared |
|---|---|---|
| capabilities | Manifest required capabilities (`05`) | absent (not granted) |
| credentials | declared credential requirements → `.env` references | none injected |
| filesystem | declared working dir + declared input artifact paths (`13`) | restricted workspace only; no host FS |
| network | declared egress/endpoints (`18` policy) | deny egress |
| compute limits | package limits / Strategy | adapter-default conservative limits |

- Capabilities are **provider-independent** (INV-32); least privilege is expressed in
  abstract capability terms, and the adapter maps the granted minimum onto the concrete
  runtime at bind.
- A package that declares *nothing* gets the **most restricted** viable profile, not a
  permissive one. Privilege is opt-in by declaration, never ambient.
- Two attempts of the same package (retries, `02` §6) each provision their own minimal
  set; a retry on a different runtime re-derives least privilege for that runtime's
  profile.

## 5. Fail-closed enforcement points

Refusal (→ `Failed`, `11`) is the only safe response to a security gap. There is no
"run anyway":

| Failure | Response |
|---|---|
| required credential missing / unresolved in `.env` | refuse session before start (fail-closed) |
| isolation profile cannot be established (e.g. container/namespace setup fails) | refuse session; no weaker boundary substituted |
| declared filesystem scope cannot be honored | refuse session |
| declared network posture cannot be enforced | refuse session (no ambient-network fallback) |
| auth/policy check returns anything but a positive allow | treat as deny (A-001-style fail-closed) |

Each refusal is a typed error (`11`) carrying the *class* of the failure and its owner
— **never the secret value** that was missing or the credential that failed.
Fail-closed is also why a *late* policy denial during preparation routes `Ready →
Destroyed` directly (`07` §3), releasing the allocation rather than proceeding.

## 6. Secret redaction in streams & artifacts

Secrets must not escape through the very channels RM supervises:

- **Streams (`08`).** stdout/stderr/structured lines are runtime-independent events;
  redaction applies as they are captured, so an injected secret echoed by a runtime
  process is masked before it becomes a `runtime.output` payload. The redaction is a
  capture-time concern (where the stream model defines its boundary), not an
  afterthought on stored data.
- **Artifacts (`13`).** Evidence Candidates / outputs are referenced by id and may be
  inspected later; redaction policy applies so a secret value cannot land in an
  artifact's content or metadata. Artifacts carry references, never embedded secret
  values (ADR-003, INV-12).
- **Events & logs.** Already covered by §3: no secret value ever enters a `runtime.*`
  payload or log line in the first place; redaction at the stream/artifact edge is the
  defense for values a *runtime itself* emits.

> Redaction protects against the runtime leaking a secret it was given; non-embedding
> protects against RM leaking a secret it injected. Both are required.

## 7. Teardown is a security boundary (tie to `07` and cleanup `09`)

Security does not end at `Completed` — it ends at `Destroyed`:

- On **every** terminal path (`Completed | Cancelled | Failed`), teardown runs (`07`
  §6): credential handles revoked, injected env scrubbed, ephemeral profiles / temp
  workspaces removed, containers torn down, processes killed.
- **Cancellation cleanup (`09`)** invokes the same credential/filesystem teardown on a
  forced or graceful stop, so an aborted session leaks no live credential and no
  residual workspace.
- A teardown that fails to revoke or clean is a **surfaced anomaly** (typed teardown
  error, `11`), not a swallowed one; the allocation is still released (`06`) so capacity
  is not leaked even when a credential cleanup is flagged for operator attention.

## 8. Invariants & ADRs this document honors

| Invariant / ADR | How honored |
|---|---|
| **least privilege (platform rule)** | session provisioned only declared capabilities/credentials/FS/network; default deny |
| **fail-closed (platform rule)** | missing credential / failed isolation refuses the session; no degraded-but-running |
| **`.env` single source of truth** | secret values live only in `.env`; injected by reference at configure-time |
| **secrets never embedded/printed** | absent from package, events, logs, streams, artifacts; treated as sensitive |
| **INV-32** capabilities provider-independent | least privilege expressed abstractly; provider mapping at adapter bind |
| **ADR-003 / INV-12** evidence by reference | artifacts referenced by id; redaction prevents secret values in content/metadata |
| **dependency direction (`00`)** | provider/isolation specifics live only behind adapters; RM core stays generic |

## 9. One-paragraph mental model

Every runtime category is its own jail with its own walls — a restricted process for
Shell/Python, a namespace-isolated container for Docker, an ephemeral sandboxed profile
for Browser, a scoped provider session for Claude/Gemini/MCP, an mTLS-trusted channel
for a remote worker — and each session is provisioned only the capabilities,
credentials, filesystem, and network its package declared, derived to the minimum.
Secrets live in `.env`, reach the runtime only as injected references through the
adapter at configure-time, never touch the immutable package or any event/log/stream/
artifact, are redacted at the stream and artifact edges if a runtime echoes them, and
are revoked when the session is destroyed. If a credential is missing or a wall cannot
be built, the session is refused, not run. RM hosts the work; it never lowers the
walls.
