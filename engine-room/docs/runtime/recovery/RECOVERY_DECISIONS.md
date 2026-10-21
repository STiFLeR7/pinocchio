# Recovery Decision Model — implementation

Milestone 1. Recovery decisions are immutable and drawn from a closed vocabulary. This
program implements the scope defined by the prompt: **Complete / Retry / Resume / Escalate /
Await Approval / Abort**. Replan is **reserved** for a later Planning integration and is not
implemented.

---

## 1. Decision vocabulary vs doc-19 strategies

Doc 19 enumerates a broader set of *Recovery Strategies*. The program's decision set is a
subset (plus `Complete`, the no-failure case). The mapping:

| Program decision (implemented) | doc-19 strategy | Notes |
|---|---|---|
| **Complete** | Continue | verdict Passed — nothing to recover |
| **Retry** | Retry | bounded by the retry policy |
| **Resume** | Resume / Checkpoint Restore | from the latest valid checkpoint |
| **Escalate** | Human Escalation | to the policy's escalation target |
| **Await Approval** | Human Review | governance / inconclusive gate (INV-22) |
| **Abort** | Abort | no governed continuation exists |
| *(deferred)* | Rollback | domain-specific; not in program scope |
| *(deferred)* | Switch Runtime | runtime failover; not in program scope |
| *(deferred)* | Request Context | context recovery; not in program scope |
| *(deferred)* Replan | — | reserved for Planning integration |

The deferred strategies are modelled where they touch the vocabulary (e.g. `FailureCategory`
covers `CONTEXT` and `DEPENDENCY`) but are **not** proposed by any rule — they route to
`Escalate` today, honestly, rather than being silently synthesised.

## 2. Decision → lifecycle stage

The plan's `stage` is a fixed projection of the decision (doc-19 *Recovery State*, the
deterministic subset):

| Decision | `RecoveryStage` |
|---|---|
| Complete | `COMPLETE` |
| Retry | `RETRY` |
| Resume | `RESUME` |
| Escalate | `ESCALATED` |
| Await Approval | `WAITING_APPROVAL` |
| Abort | `ABORTED` |

The *execution* stages of doc-19 (`Restoring` / `Retrying` / `Recovered`) belong to the actor
that performs the action, not the decision layer — Recovery reaches the decision stage and
stops (INV-21: "Recovery decides continuation").

## 3. Verdict → decision (the common paths)

Under the default policy, with the default rules:

| Validation verdict | Failure | Checkpoint | Decision |
|---|---|---|---|
| Passed | — | — | **Complete** |
| Requires Review | any | any | **Await Approval** |
| Failed | governance | — | **Await Approval** |
| Failed / Partial | runtime / resource / validation | — | **Retry** (budget) → **Escalate** (exhausted) |
| Partial | any | present | **Resume** |
| Failed / Partial | context / dependency | — | **Escalate** |
| any | any (category ∈ policy.abort_on) | — | **Abort** |

## 4. Determinism guarantees

The decision, its derivation, and the plan are pure functions of `(report, result, policy,
attempt, checkpoint)` — identical inputs always produce an identical decision. There is no
clock, no randomness, and no AI in the decision path (verified by the determinism tests).
