# 10 — Timeout Model

**Status:** design only. Defines the four kinds of timeout the Runtime Manager (RM)
enforces while supervising a session — **execution**, **inactivity**, **policy**, and
**heartbeat** — including for each the **source of its bound**, the **signal that resets
it**, what **firing** does, and who **owns** it. Timeouts are **declarative inputs RM
enforces**, never numbers RM invents; a fired timeout is, by canon, a **recoverable
failure** to the future Recovery subsystem — RM only **records** it and **ends** the
session.

---

## 1. Principle: declared, not chosen

Every timeout bound originates **outside** RM, as a declarative value:

- **Execution / inactivity / heartbeat** bounds come from the **Execution Strategy's
  `timeout_policy`** (`domain/execution_strategy.py`: *"Maximum execution / waiting /
  retry durations; timeout elapse is a recoverable failure"*). RM **reads** this
  declarative `Struct`; it does **not** evaluate verdicts from it and does **not** pick
  the numbers.
- **Policy** bounds come from **governance** (`18`) — a governance-imposed maximum, of
  the same declarative nature.

RM's role is **enforcement**: arm the bound, watch for its reset signal, and act when it
elapses. This mirrors the platform spine — *declaration ≠ evaluation* (ADR-004): the
Strategy and governance **declare**; RM **applies**. RM never raises, lowers, or skips a
bound on its own; an absent bound means *no timeout of that kind is armed*, not a
default RM fabricates.

> A timeout is a **clock RM watches**, not a **decision RM makes**. When it fires, RM
> records the fact (`runtime.timed_out`) and ends the session via cancellation (`09`).
> Whether the work is then re-attempted is Recovery's call (`enums.RetryBehavior`,
> `enums.RecoveryBehavior`) — a separate later phase.

## 2. The four timeout kinds

### 2.1 Execution timeout (max total wall-time)

The ceiling on **total wall-clock** for the whole attempt, end to end.

- **Source of bound:** Execution Strategy `timeout_policy` (max execution duration).
- **Reset signal:** *none* — it is an absolute budget measured from the start of
  `Running`; activity does not extend it. It is the one bound the runtime cannot "earn
  back" by being busy.
- **On fire:** the attempt has run too long overall → emit `runtime.timed_out`
  `{ timeout_kind: execution }` → escalate via `09`.
- **Owner:** RM enforces; Strategy (Planning) declares.

### 2.2 Inactivity timeout (no stream/heartbeat for N)

Fires when the session produces **no observable activity** for the declared interval —
distinct from the total budget: a session can be well under its execution timeout yet be
*stuck* and silent.

- **Source of bound:** Execution Strategy `timeout_policy` (waiting/idle duration).
- **Reset signal:** any **activity event** that advances the session's *last-activity*
  marker (`02` §5) — a stream chunk (`runtime.output`, `08`), a progress update
  (`runtime.progress`, `12`), an artifact emission (`runtime.artifact_emitted`, `13`), or
  a heartbeat (`runtime.heartbeat`). Each such event resets the inactivity clock.
- **On fire:** the runtime is presumed *stalled* (compare `enums.OperationalHealth.STALLED`)
  → emit `runtime.timed_out` `{ timeout_kind: inactivity }` → escalate via `09`.
- **Owner:** RM enforces; Strategy declares. (Ties to the streaming/progress last-activity
  signal in `08`/`12`.)

### 2.3 Policy timeout (governance-imposed max)

A **governance** ceiling, imposed independently of what the Strategy declared — e.g. a
cost/wall-time cap a governance policy enforces on a class of runs (`18`).

- **Source of bound:** Governance policy (`18`), not the Strategy.
- **Reset signal:** *none* — like the execution timeout it is an absolute governance
  budget; activity does not extend a governance cap.
- **On fire:** governance's maximum is reached → emit `runtime.timed_out`
  `{ timeout_kind: policy }` → escalate via `09`. A policy timeout commonly maps to a
  governance-reason cancellation (`09` §2, *policy-denied*).
- **Owner:** RM enforces; Governance (`18`) declares.

### 2.4 Heartbeat timeout (liveness ping missing)

Fires when an expected **liveness ping is missing**, so the runtime is presumed **dead**
(crashed, partitioned, or transport-severed) rather than merely slow.

- **Source of bound:** Execution Strategy `timeout_policy` (heartbeat interval/tolerance),
  applicable only to runtimes whose adapter advertises a heartbeat capability (`05`).
- **Reset signal:** each received `runtime.heartbeat` (`15`) — the liveness ping itself.
- **On fire:** the runtime is presumed **dead** → emit `runtime.timed_out`
  `{ timeout_kind: heartbeat }` → escalate via `09`. Because the runtime is presumed
  gone, graceful cancellation usually cannot take effect and escalation proceeds to a
  forced teardown (`09` §3.2).
- **Owner:** RM enforces; Strategy declares; the adapter (`03`) supplies the heartbeat
  signal.

> Inactivity vs heartbeat: **inactivity** means *"the runtime is alive but produced
> nothing"*; **heartbeat** means *"the runtime stopped telling us it is alive at all."*
> They are different liveness questions and may be armed independently.

## 3. Summary table

| Kind | Bound source | Reset signal | On-fire action |
|---|---|---|---|
| **Execution** | Strategy `timeout_policy` (max total wall-time) | *none* (absolute budget from `Running`) | `runtime.timed_out{execution}` → escalate (`09`) |
| **Inactivity** | Strategy `timeout_policy` (idle/waiting) | any activity: output / progress / artifact / heartbeat (`08`/`12`/`13`) | `runtime.timed_out{inactivity}` → escalate (`09`) |
| **Policy** | Governance policy (`18`) | *none* (absolute governance cap) | `runtime.timed_out{policy}` → escalate (`09`) |
| **Heartbeat** | Strategy `timeout_policy` (heartbeat tolerance) | each `runtime.heartbeat` (`15`) | `runtime.timed_out{heartbeat}` → escalate (`09`) |

All four are **declarative in, enforcement out**: the left two columns are inputs RM
reads; the right two are the only things RM *does*.

## 4. What firing does (the common path)

Every timeout, regardless of kind, follows the same enforcement sequence:

```
bound armed at start of supervision (per kind; only if declared)
        │
        │  reset signals keep the relevant clock alive (per §2)
        ▼
bound elapses ─► emit runtime.timed_out { timeout_kind }     (record the fact, 15)
        │
        ▼
escalate via the Cancellation Model (09):
        graceful stop (grace window) ─► if not stopped ─► forced stop
        │
        ▼
terminal state:
   • Cancelled  (RM resolves the timeout by stopping the attempt)  ─► Destroyed
   • Failed     (where the Strategy/policy classifies the elapsed
                 bound as a typed error, 11)                       ─► Destroyed
        │
        ▼
release allocation + adapter cleanup ─► runtime.released ─► runtime.destroyed (07)
```

- `runtime.timed_out` is recorded **first** and always (`15`); it *precedes* the
  cancel/fail and names the `timeout_kind`. It is the durable evidence that a bound was
  hit, available to Recovery, Observability (`16`), and Governance/audit (`18`).
- Escalation is delegated wholesale to `09`; the timeout model does not re-specify
  graceful/forced mechanics.
- **State outcome.** A timeout RM resolves by stopping the attempt yields `Cancelled`
  (`07`). Where the declared classification treats the elapsed bound as a typed failure,
  the outcome is `Failed` (`11`). RM **follows the declared classification**; it does not
  choose between `Cancelled` and `Failed` on its own initiative. Either way the session
  always reaches `Destroyed` (`07` §6).

## 5. Timeouts are recoverable failures (RM records, does not recover)

By canon (the Strategy docstring: *"timeout elapse is a recoverable failure"*), a fired
timeout is the kind of failure the future **Recovery** subsystem is meant to handle —
e.g. by selecting `FIXED_RETRY`, `EXPONENTIAL_RETRY`, `RUNTIME_SWITCH`, or
`HUMAN_ESCALATION` (`enums.RetryBehavior`), or `RETRY`/`ESCALATE`/`ABORT`
(`enums.RecoveryBehavior`). **RM does none of that.** RM's entire contribution is:

1. enforce the declared bound;
2. emit `runtime.timed_out` (the recoverable-failure fact);
3. end the session via `09` to a terminal state;
4. always reach `Destroyed`.

The retry/switch/escalate decision is made downstream from the recorded fact (`15` §5:
*Recovery reacts to `runtime.failed` / `runtime.timed_out`*). RM never re-arms a bound to
"try a bit longer," never silently extends a deadline, and never decides to re-attempt —
all of which would be invented policy.

## 6. Ownership

| Concern | Owner |
|---|---|
| Declaring execution/inactivity/heartbeat bounds | Execution Strategy `timeout_policy` (Planning) |
| Declaring the policy/governance cap | Governance (`18`) |
| Arming, watching, and resetting the clocks | RM (control plane) |
| Supplying the heartbeat liveness signal | the Runtime Adapter (`03`) |
| Recording the fired fact | RM, as `runtime.timed_out` (`15`) |
| Escalating to a terminal state | RM, via `09` |
| Deciding what happens *after* a timeout | Recovery (future) — **not** RM |

Determinism note: the bounds are *durations*, but RM measures them against an **injected
timestamp source** (INV-17); wall-clock values live only in event payloads, and the
session's value objects stay timestamp-free (`01` §5, `02` §5). A replay of a session's
event log reproduces the same timeout outcome because the firing is recorded as a fact,
not recomputed from a live clock.

---

### Cross-references

- `01_RUNTIME_MANAGER.md` — supervision step 13 enforces timeouts.
- `02_RUNTIME_SESSION.md` — the *last-activity* marker the inactivity timeout reads.
- `03_RUNTIME_ADAPTERS.md` — the adapter supplies the heartbeat signal.
- `07_RUNTIME_LIFECYCLE.md` — terminal `Cancelled`/`Failed` and the `Destroyed` guarantee.
- `08_STREAMING_MODEL.md` — stream chunks reset the inactivity clock.
- `09_CANCELLATION_MODEL.md` — how a fired timeout escalates graceful→forced.
- `11_ERROR_MODEL.md` — when an elapsed bound is classified as a typed failure.
- `12_PROGRESS_MODEL.md` — progress updates reset the inactivity clock.
- `13_ARTIFACT_MODEL.md` — artifact emissions reset the inactivity clock.
- `15_RUNTIME_EVENTS.md` — `runtime.timed_out`, `runtime.heartbeat`.
- `16_RUNTIME_OBSERVABILITY.md` — timeout metrics and timelines.
- `18_RUNTIME_GOVERNANCE.md` — the source of the policy timeout.
