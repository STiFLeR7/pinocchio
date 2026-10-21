# Runtime Decisions — engineering choices for the vertical slice

Each decision below is an *engineering* choice made within the frozen architecture. Where a
choice touched the frozen Runtime Core, its architectural justification is stated. None
modified an ADR, contract, invariant, or `docs/v2/runtime/00`–`24` document.

---

## 1. Realize the deferred execution-lifecycle canon inside `nexus_runtime`

**Decision.** Implement the execution/teardown states (`Running`, `Completed`, `Cancelled`,
`Destroyed`) and events (`runtime.started`, `runtime.output`, `runtime.progress`,
`runtime.artifact_emitted`, `runtime.timed_out`, `runtime.completed`, `runtime.cancelled`,
`runtime.destroyed`) in `nexus_runtime/{vocabulary,events,lifecycle}.py`.

**Why this is not an architecture change.** Docs `07` (lifecycle) and `15` (events) already
define these states and events as **canon**. Phase 8A did not add or remove them — it
*deferred implementing* them, with explicit forward references in the code
(`lifecycle.py`, `vocabulary.py`, `events.py`: "deferred to the Execution Engine phase").
The Execution Engine phase is *this* program, so realizing them **fulfils** the frozen spec
rather than altering it. The state vocabulary lives in the layer that already owns the
Runtime Session and its lifecycle projection (`02`/`07`), preserving a single canonical
state machine and a single event taxonomy.

**Alternative rejected.** Modelling execution states in a second, engine-local machine
(keeping `nexus_runtime` byte-frozen) would fork lifecycle ownership away from the Session's
owner and duplicate the projection — a worse architectural outcome. Chosen only after
explicit ratification of the "realize in `nexus_runtime`" reading.

**Scope discipline.** Added `Running/Completed/Cancelled/Destroyed` only. `Paused`/`Waiting`
(suspend/resume/approval-block) stay deferred — the minimal engine implements no scheduling,
recovery, or approval pause, so driving those canonical states is out of scope. `Released`
remains the preparation-abandon terminal; `Destroyed` is the executed-session teardown
terminal (`07` §6).

## 2. Deterministic stub Claude for CI; real `claude` for an opt-in smoke

**Decision.** The automated E2E drives a deterministic `StubClaudeInvoker` through the
**real** adapter seam; a separate, environment-gated test
(`NEXUS_CLAUDE_SMOKE=1`) shells to the real `claude` CLI.

**Why.** The program requires a *deterministic event stream*, but a real model's output is
non-deterministic and needs auth/network. Determinism is a property of event **ordering and
shape**, not of the model's text — so a deterministic runtime behind the same adapter proves
the architecture, while the real-CLI path proves the wire integration on demand. The stub is
a pure function of the rendered prompt (no clock, no randomness), so two runs are
byte-identical under a `FixedTimestampSource`.

## 3. A separate generic `nexus_execution` package for the Engine

**Decision.** The Execution Engine and the concrete `RuntimeAdapter` protocol live in a new
provider-agnostic package; `nexus_runtime_claude` implements the protocol.

**Why.** Doc `00` §7 defines the Execution Engine as a distinct downstream subsystem,
generic across runtimes. Keeping it separate satisfies the validation checklist directly
("RM contains zero Claude code / the adapter has all provider behavior") and makes a second
runtime a new adapter package with no engine change.

## 4. Integration-boundary assembly for the E2E pipeline

**Decision.** Assemble the Execution Package as a `RuntimeIntake` at the sanctioned
integration boundary (`requests.py`'s documented pattern) and prepare it through the real RM
pipeline, rather than driving a literal Goal through Planning→…→Harness.

**Why.** `requests.py` explicitly states RM consumes a `RuntimeIntake` "assembled at the
integration boundary (which may import the upstream layers)." This proves the
Harness→Runtime→Engine→Claude seam deterministically without rebuilding the whole upstream
pipeline inside the test (which would surface unrelated upstream-completeness gaps outside
this program's target). The full Goal→Harness path remains available for a later, broader
integration program.

## 5. Materializing the conceptual adapter contract (doc 03)

**Decision.** Turn doc `03`'s *conceptual* nine-concern contract into a concrete
`typing.Protocol` (`nexus_execution/adapter.py`), mapping each member 1:1 to a concern
A–I, coining no new lifecycle state or event.

**Why.** Doc `03` deliberately specifies "no interface signature, no method list" — leaving
the concrete seam an *engineering* decision (which the readiness review says Phase 8A
requires). The Protocol keeps the engine generic (`isinstance(adapter, RuntimeAdapter)`) and
provider-blind while giving the adapter a precise, testable contract. Cancellation/timeout
are cooperative via an `ExecutionControl` the engine also enforces (graceful-then-forced,
`09`); the timeout bound is a deterministic per-signal `deadline_steps` (the clock-free model
of `10`'s wire/inactivity bound).

## 6. Known, non-blocking future affordance — capacity release for executed sessions

`RM.release()` returns capacity by moving a session to `Released` (the preparation-abandon
terminal). An *executed* session's terminal state is `Destroyed`, so returning its
allocation capacity needs a small RM affordance that emits `runtime.released` **without**
forcing the `Released` state (capacity is a Registry concern, INV-36). The minimal engine
(Milestone-3 scope: "only execute") does not manage capacity; it drives adapter cleanup to
`Destroyed`. This is a documented engineering follow-up for the full Execution Engine phase —
**not** an architectural conflict (no ADR/contract/invariant blocks it; doc `07` §6 already
separates `runtime.released` the *event* from the teardown *state*).
