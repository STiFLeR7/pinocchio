# 02 — Runtime Session

**Status:** design only. Defines the central stateful object of the subsystem — the
Runtime Session — including its identity, ownership, the state it maintains, how it
survives retries, and how checkpoints, logs, and artifacts attach to it.

---

## 1. What a session is

A **Runtime Session** is the stateful instance that binds **one Execution Package** to
**one allocated runtime** for **one execution attempt**. It is the unit RM creates,
owns, supervises, and destroys, and the artifact it hands to the Execution Engine.

A session is the runtime-layer analogue of the Orchestration **Execution Session**
(which binds Goal/Context/Plan/Graph/Strategy) — but one level lower: it binds a single
compiled package to a single concrete runtime. Like the Execution Session, it has **no
frozen core contract** today (it is a Runtime-layer output); see `ARCHITECTURE_REVIEW.md`
(observation, mirrors Phase-5 O-7).

> A session is a *binding and a lifecycle*, not the work and not the runtime. It
> references the package (by id) and the allocated runtime (by id); it never embeds the
> package's content or the runtime's implementation.

## 2. What it binds (by reference, never embedded)

| Field (conceptual) | Points to | Source |
|---|---|---|
| execution_package_ref | the compiled package | Harness |
| work_package_ref | the embedded Work Package (what runs) | Harness/Planning |
| context_view_ref | the immutable Context View | Harness/Context |
| runtime_ref | the **allocated** runtime descriptor | Registry (after allocation) |
| allocation_ref | the reservation record | RM (`06`) |
| execution_strategy_ref | governing Strategy (timeouts, retry, approval) | Harness/Planning |
| correlation | the operation-wide correlation/trace lineage | upstream, carried through (INV-39) |
| attempt | the retry attempt ordinal | RM |
| checkpoints | references to checkpoints taken | RM/Recovery (`07`, ADR-001) |
| artifacts | references to Evidence Candidates / outputs emitted | runtime via adapter (`13`) |

Everything is a typed reference. The session is small and immutable-by-construction;
its **current state** is a projection of the `runtime.*` event log (ADR-001), not a
mutable field bag (see §5).

## 3. Identity & identifiers

Identifiers are **pure functions** of stable upstream identities and the attempt
ordinal — no clock, no counter, no randomness — so preparation is reproducible and a
replay yields the same names (mirrors Harness/Orchestration `ids`):

- **session id** — derived from the Execution Package identity (which itself derives
  from the Harness Request → session → node chain) plus the attempt ordinal. One
  package + one attempt ⇒ one stable session id.
- **allocation id** — derived from the session id and the chosen runtime identity.
- **event ids** — derived from the session id, an event-kind tag, and a monotonic
  sequence within the session (so the stream is ordered and dedup-keyed, INV-16).

Because the attempt ordinal is part of the session id, **a retry is a new session with
a new, deterministic id** — not a mutation of the prior one (§6).

## 4. Ownership & lifetime

- **Owner:** the Runtime Manager owns the session for its entire life — creation
  through destruction — including while the Execution Engine runs the work *within* it.
  Ownership does not transfer at handoff; only *driving the work* does.
- **Created when:** RM has selected and allocated a runtime for a package (pipeline step
  9, `01`).
- **Destroyed when:** the attempt reaches a terminal state (`Completed`, `Cancelled`,
  or `Failed`) and RM has released the allocation and run adapter cleanup (`07`, `09`).
- **One attempt:** a session models a *single* attempt. Multiple attempts of the same
  package are multiple sessions sharing a correlation lineage (§6).

## 5. State it maintains (as a projection)

Per ADR-001, the authoritative state is the `runtime.*` event log; the session's
"current state" is a **projection** folded from it (idempotent, INV-16; deterministic
on replay). The projection exposes, at minimum:

- **lifecycle state** — one of the canonical states in `07` (`Created … Destroyed`).
- **allocation state** — `ResourceAllocationState` (`AVAILABLE → RESERVED → ALLOCATED →
  RELEASED`).
- **progress** — latest progress snapshot (`12`), which may be *unknown*.
- **last activity** — the timestamp of the most recent stream/heartbeat event, for
  inactivity-timeout reasoning (`10`).
- **artifact set** — references accumulated so far (`13`).
- **error** — the typed error if a terminal failure occurred (`11`).

RM holds no hidden mutable truth outside the log; restoring the projection from the log
(optionally from a snapshot plus tail replay) reconstructs the session exactly
(INV-14/18).

## 6. Surviving retries

RM does **not** perform recovery — it does not decide to retry (Recovery does, a later
phase). But the *session model* must make retry expressible and clean:

- A retry of package *P* is a **new session** `attempt = n+1` with a new deterministic
  id; the prior session remains in the log as an immutable, terminal record.
- All attempts share the **correlation** lineage, so the full attempt history of a
  package is queryable as one causal stream (INV-39).
- A new attempt may **resume from a checkpoint** (§7) rather than starting cold, when
  the runtime/adapter supports it and a recovery checkpoint exists. RM exposes the
  checkpoint reference to the adapter at configuration; whether to use it is the
  Recovery/Strategy decision, surfaced as input — RM does not invent it.
- Allocation is per-attempt: each session allocates (and later releases) its own
  runtime; a retry may land on a **different** runtime from the candidate set.

## 7. Checkpoints

Checkpoints are the platform's recovery substrate (ADR-001, INV-18). In the runtime
layer:

- A **checkpoint** is a referenced, point-in-time capture associated with a session
  (e.g. captured progress, partial artifacts, runtime-reported resumable state). It is
  recorded as data and referenced by id — never embedded.
- RM **associates** checkpoints with the session and emits a checkpoint event; it does
  not decide checkpoint *frequency* or *recovery use* — those come from the Execution
  Strategy's `checkpoint_policy` and Recovery, respectively. RM is the mechanism, not
  the policy.
- On a new attempt, a `recovery checkpoint` reference can be supplied to the adapter so
  a capable runtime resumes rather than restarts (§6).

## 8. Logs & artifacts association

- **Logs/streams** (`08`) are runtime-independent events carrying stdout/stderr/
  structured lines, each stamped with the session id and sequence, so a session's full
  output is reconstructable from the log alone.
- **Artifacts** (`13`) — files, logs-as-artifacts, metrics, structured outputs,
  execution metadata — are emitted by the runtime through the adapter as **Evidence
  Candidates**, referenced by id on the session (INV-12: referenced, never embedded).
  RM collects and associates them; **Validation** later promotes Evidence Candidates to
  Evidence and renders the completion verdict (INV-20). RM never grades artifacts.

## 9. What a session is *not*

- Not the Work Package (it *references* one).
- Not the runtime (it *references* an allocated one).
- Not the Execution Engine (which *runs within* it).
- Not a verdict of success (that is Validation's, from Evidence).
- Not durable beyond its attempt (terminal → released → destroyed), though its event
  record is permanent in the log.
