# 11 — Error Model

**Status:** design only. Defines the taxonomy of runtime errors the Runtime Manager (RM)
recognizes, **where each arises** in the preparation/supervision pipeline (`01`), the
**lifecycle transition** it triggers (`07`), **who owns** it (RM-classified vs
adapter-surfaced vs infra-surfaced), and **who consumes** it downstream. The governing
discipline: **fail-fast, no silent correction, always reach `Destroyed`.** RM
**classifies** a failure and **emits `runtime.failed`**; it **never decides recovery** —
that is a separate later phase.

---

## 1. Principles

- **Fail-fast.** The moment a step cannot proceed correctly, RM stops that session with a
  *typed* error; it never limps forward on a guessed default (`01` §4: a failure at any
  pipeline step short-circuits to RELEASE + DESTROY).
- **No silent correction.** RM never substitutes, retries, or "fixes" a failure quietly.
  Every failure becomes a recorded `runtime.failed` fact with an `error_class` and an
  `owner` (`15`).
- **Always reach `Destroyed`.** A typed error takes the session to `Failed`, then
  *unconditionally* to `Destroyed` via release + adapter cleanup (`07` §6). Teardown is
  guaranteed even when the failure occurred *during* teardown.
- **Classify, do not decide.** RM's responsibility ends at *naming* the failure and
  emitting it. What to do next — retry, switch runtime, escalate, abort
  (`enums.RetryBehavior`, `enums.RecoveryBehavior`) — is Recovery's, downstream of the
  emitted fact (`15` §5). RM **does not recover**.
- **One terminal exception.** Every error class drives `→ Failed`, **except
  user-cancellation**, which is the intentional-stop path and drives `→ Cancelled` (`09`),
  not `Failed`.

## 2. Error classes

Each class below states its **definition**, **where it arises** (pipeline step from `01`
§4), the **transition** it triggers, its **owner** (who first surfaces/classifies it),
and its **downstream consumer**.

### 2.1 runtime-unavailable
- **Definition:** no eligible candidate runtime is healthy/available to host the package
  — the candidate set is empty after health filtering, or all candidates are
  `OFFLINE`/`FAILED`/`MAINTENANCE` (`enums.ResourceAvailability`).
- **Arises at:** intake/health (steps 1–4: VALIDATE INTAKE → RESOLVE CANDIDATES → MATCH
  CAPABILITIES → FILTER HEALTH).
- **Transition:** `Created → Failed` (or abandon to `Destroyed` if pre-`Created`).
- **Owner:** RM-classified (read from the Registry view, INV-36; RM names the failure).
- **Consumer:** Recovery (e.g. `RUNTIME_SWITCH`/retry-later) and Governance/audit.

### 2.2 allocation-failure
- **Definition:** a runtime was selected but could not be **reserved/allocated** —
  contention, capacity exhaustion, or a lost race on the `ResourceAllocationState`
  reservation (`06`).
- **Arises at:** allocation (step 8: ALLOCATE).
- **Transition:** `Created → Failed` (allocation precedes session `Prepared`).
- **Owner:** RM-classified (RM owns selection + allocation, `01` §2.5).
- **Consumer:** Recovery (retry / different candidate) and capacity accounting (`06`).

### 2.3 execution-startup-failure
- **Definition:** the allocated runtime could not be **brought up** for execution —
  configuration could not be rendered/applied, the runtime process/container/browser
  failed to start, or readiness checks never passed.
- **Arises at:** configure / ready / handoff-start (steps 10–12: CONFIGURE → READY →
  HANDOFF, and the engine's `Ready → Running` start).
- **Transition:** `Prepared → Failed` or `Ready → Failed` (a pre-start failure; `07` §4).
- **Owner:** Adapter-surfaced (the provider reports it), RM-classified into this class.
- **Consumer:** Recovery (retry / switch runtime).

### 2.4 transport-failure
- **Definition:** the communication channel to the runtime broke — a severed socket/pipe,
  a lost remote-worker connection, or stream transport collapse (`08`) — so RM can no
  longer drive or observe the session.
- **Arises at:** supervision (step 13: SUPERVISE), while `Running`/`Paused`/`Waiting`.
- **Transition:** `Running → Failed` (also reachable from `Paused`/`Waiting`).
- **Owner:** Adapter-surfaced (the adapter owns the transport, `03`); RM-classified.
- **Consumer:** Recovery (retry / switch runtime). *Note:* a transport break that
  manifests only as missing liveness is detected as a **heartbeat timeout** (`10`) and
  flows through `runtime.timed_out` first.

### 2.5 provider-failure
- **Definition:** the runtime itself failed at the provider level — the runtime crashed,
  the provider returned an internal/usage error, an authentication/quota rejection from a
  backing service, or the process exited abnormally for a runtime-internal reason.
- **Arises at:** supervision (step 13), while `Running`.
- **Transition:** `Running → Failed`.
- **Owner:** Adapter-surfaced (the provider is the origin, `03`); RM-classified.
- **Consumer:** Recovery (retry / switch / escalate) and Observability (`16`).
  *Boundary:* an abnormal exit is `provider-failure → Failed`; a **normal** process end
  is `runtime.completed → Completed` (not validated, INV-20) — never an error.

### 2.6 infrastructure-failure
- **Definition:** a Nexus-platform substrate fault unrelated to the runtime — event
  store/bus unavailability, repository fault, or workspace/filesystem provisioning
  failure in the Phase 2 substrate that RM depends on.
- **Arises at:** any step (the substrate underlies the whole pipeline, `00` §4).
- **Transition:** `* → Failed` (from whatever state was current; abandon to `Destroyed`
  if pre-`Created`).
- **Owner:** Infra-surfaced (`nexus_infra`); RM-classified into this class.
- **Consumer:** Recovery and platform operations/Observability (`16`).

### 2.7 user-cancellation
- **Definition:** an intentional, operator/governance/supervisor-initiated stop — **not a
  fault**. It is included in the taxonomy for completeness but is the one class that does
  **not** end in `Failed`.
- **Arises at:** supervision (step 13), or preparation-abandon before handoff (`09` §5).
- **Transition:** `Running/Paused/Waiting → Cancelled` (or `Ready → Destroyed` if
  abandoned pre-start; `07`/`09`).
- **Owner:** RM-enforced (`09`); the *reason* originates with the initiator (operator /
  governance / supervisor / timeout).
- **Consumer:** Recovery (decides whether the cancelled attempt is retried) and
  Governance/audit. Emitted as `runtime.cancelled`, **not** `runtime.failed`.

### 2.8 timeout (cross-reference)
- **Definition:** a declared bound elapsed — execution, inactivity, policy, or heartbeat
  (`10`). Specified fully in `10_TIMEOUT_MODEL.md`; listed here for taxonomy completeness.
- **Arises at:** supervision (step 13).
- **Transition:** emit `runtime.timed_out` → escalate via `09` → `Cancelled` (RM resolves
  by stopping) **or** `Failed` (where the declared classification treats the elapsed bound
  as a typed error). Either way → `Destroyed`.
- **Owner:** RM-enforced (bound declared by Strategy/governance, `10` §6).
- **Consumer:** Recovery — a timeout is a **recoverable failure** by canon (`10` §5).

## 3. Ownership table

| Error class | Arises at (`01` step) | Session outcome | Owner | Downstream consumer |
|---|---|---|---|---|
| runtime-unavailable | 1–4 intake/health | `Failed` | RM-classified (Registry, INV-36) | Recovery; Governance/audit |
| allocation-failure | 8 allocate | `Failed` | RM-classified (`06`) | Recovery; capacity accounting |
| execution-startup-failure | 10–12 configure/ready/start | `Failed` | Adapter-surfaced → RM-classified | Recovery |
| transport-failure | 13 supervise | `Failed` | Adapter-surfaced → RM-classified | Recovery |
| provider-failure | 13 supervise | `Failed` | Adapter-surfaced → RM-classified | Recovery; Observability |
| infrastructure-failure | any step | `Failed` | Infra-surfaced → RM-classified | Recovery; platform ops |
| user-cancellation | 13 / pre-handoff | `Cancelled` | RM-enforced (`09`) | Recovery; Governance/audit |
| timeout (`10`) | 13 supervise | `Cancelled` *or* `Failed` | RM-enforced (Strategy/gov-declared) | Recovery |
| teardown error (§4) | 14 release/destroy | still `Destroyed` (recorded) | Adapter/Infra-surfaced → RM-classified | Recovery; platform ops |

*"Owner" = who first surfaces the fault.* In every row, **RM is the classifier** — it
maps the surfaced fault to an `error_class` and emits the typed event. **No row makes RM
the recoverer.**

## 4. Teardown errors (a failure during cleanup)

A failure in teardown itself — adapter cleanup couldn't kill the process, the workspace
couldn't be freed, the credential handle couldn't be revoked (`09` §6, `17`) — is a typed
error too, but it is special: it **does not block** reaching `Destroyed`. The session
**still** terminates at `Destroyed` (`07` §6); the teardown error is recorded as its own
`runtime.failed` fact so the leak/anomaly is **surfaced, never hidden**. This is the
no-silent-correction rule applied to the one place where stopping would itself be a leak.

## 5. Emission and the recovery boundary

For any failure (except the intentional `user-cancellation`, which emits
`runtime.cancelled`), RM emits **`runtime.failed`** (`15`) carrying at minimum
`{ session, error_class, owner, detail }`. That event is the **handoff to Recovery** and
the **end of RM's involvement** in that attempt:

```
fault surfaced (RM / adapter / infra)
        │
        ▼
RM CLASSIFIES → error_class + owner                 (fail-fast; no silent correction)
        │
        ▼
emit runtime.failed { session, error_class, owner, detail }     (15)
        │
        ▼
state → Failed ─► release allocation + adapter cleanup ─► runtime.released
        │                                                        │
        ▼                                                        ▼
   Destroyed  ◀──────────────────────────────────────── runtime.destroyed (07)
        │
        ▼
Recovery (future) reads runtime.failed and DECIDES what next     (RM does not)
```

- **RM does not decide recovery.** It does not choose retry, runtime-switch, escalation,
  or abort; those are `enums.RetryBehavior` / `enums.RecoveryBehavior` verdicts that
  Recovery selects from the declarative Strategy `retry_policy` / `recovery_policy`.
  Recovery is a **separate later phase** (`00` §boundary table).
- **RM does not validate.** A `Failed` outcome is not the same as "the work did not
  succeed"; even a `Completed` process is *unvalidated* (INV-20). RM reports *process
  outcome*, never a verdict.
- **The event is the seam.** Everything after `runtime.failed` is a consumer reacting to
  the log (`15` §5), which is a one-way source of truth — consumers never write back into
  RM's session state.

## 6. Why these classes (and not provider-specific ones)

The taxonomy is deliberately **provider-independent**: `provider-failure` and
`transport-failure` cover *Claude Code returned an error*, *the Docker container OOM-killed
itself*, *the browser driver crashed*, *the remote worker dropped*, and *an unknown future
runtime misbehaved* — without RM's core knowing which. The provider-specific detail
travels in the adapter-surfaced `detail` payload, behind the `03` boundary; RM's core only
ever sees one of the abstract classes above. This is the error-model expression of the
subsystem's central rule — **RM core stays generic; provider knowledge lives only in
adapters** (`00` §4, `03`, `19`).

---

### Cross-references

- `00_RUNTIME_OVERVIEW.md` — boundary table placing Recovery as a separate subsystem.
- `01_RUNTIME_MANAGER.md` — the pipeline steps where each class arises; fail-fast on any step.
- `02_RUNTIME_SESSION.md` — the session's typed `error` field in the projection.
- `03_RUNTIME_ADAPTERS.md` — adapter-surfaced faults and provider `detail`.
- `06_RUNTIME_SELECTION.md` — allocation and the `ResourceAllocationState` reservation.
- `07_RUNTIME_LIFECYCLE.md` — `Failed`/`Cancelled` states and the `Destroyed` guarantee.
- `08_STREAMING_MODEL.md` — transport carrying streams that may collapse.
- `09_CANCELLATION_MODEL.md` — the `user-cancellation` path and teardown cleanup.
- `10_TIMEOUT_MODEL.md` — the timeout class and its `Cancelled`/`Failed` outcomes.
- `15_RUNTIME_EVENTS.md` — `runtime.failed`, `runtime.cancelled`, `runtime.timed_out`.
- `16_RUNTIME_OBSERVABILITY.md` — failure metrics and traces.
- `17_RUNTIME_SECURITY.md` — credential/workspace teardown that may itself error.
- `18_RUNTIME_GOVERNANCE.md` — governance-originated stop reasons.
