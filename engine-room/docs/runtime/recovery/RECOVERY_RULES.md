# Recovery Rules & Aggregation — implementation

Milestone 2. Rules are deterministic, policy-driven, and explainable — **no AI, no
heuristics** (doc 19 *Strategy Driven* / *Explainable*). Each rule is a pure function of the
`RecoveryContext` (the Validation Report, the classified failure, the policy, the attempt
count, and any checkpoint) and either *applies* (proposing exactly one `RecoveryDecision` with
a rationale) or reports `NOT_APPLICABLE`.

---

## 1. Failure classification (doc 19 *Failure Categories*)

`FailureClassifier` maps the outcome onto one `FailureCategory`, deterministically:

| Signal | Category |
|---|---|
| verdict is Passed | `NONE` (nothing to recover) |
| `error_class` ∈ {timeout, provider-failure, execution-startup-failure, teardown-failure} / owner runtime\|provider | `RUNTIME` |
| `error_class` ∈ {transport-failure, infrastructure-failure} / owner transport\|infrastructure | `RESOURCE` |
| `error_class` = user-cancellation / owner user | `GOVERNANCE` |
| unknown `error_class`, known owner | owner's category |
| unknown `error_class` and owner | `RUNTIME` (default) |
| not Passed, **no** typed execution error | `VALIDATION` (tests failed / review rejected / inconclusive) |

The execution error is authoritative when present; a non-Passed verdict with no execution
error is a `VALIDATION` failure. `CONTEXT` and `DEPENDENCY` are modelled in the vocabulary
(doc 19) and reachable via policy, but the minimal classifier does not synthesise them from
the current signals — see `LESSONS_LEARNED.md`.

## 2. The default rules

| Rule id | Applies when | Proposes |
|---|---|---|
| `recovery_completion` | verdict is Passed | **Complete** |
| `recovery_approval` | verdict is Requires Review, **or** policy requires approval for the category | **Await Approval** |
| `recovery_abort` | failure present **and** policy marks its category fatal | **Abort** |
| `recovery_resume` | verdict is Partial **and** resume allowed **and** a checkpoint exists | **Resume** |
| `recovery_retry` | failure is retryable under policy **and** retry budget remains | **Retry** |
| `recovery_escalation` | any failure (the floor) | **Escalate** |

Retryable categories (`policy.py`): `RUNTIME`, `RESOURCE`, `VALIDATION`. `CONTEXT` /
`GOVERNANCE` / `DEPENDENCY` are not plain-retryable — they route to Approval or Escalate,
never a silent re-run.

## 3. Retry policy (doc 19 — never indefinite)

`RetryPolicy(kind, max_attempts)` bounds retries explicitly. `retries_enabled` is false when
`kind is NEVER` or `max_attempts <= 1`. `attempts_remaining = max(0, max_attempts - attempt)`.
Kinds mirror doc 19 (`NEVER` / `FIXED` / `EXPONENTIAL` / `PROGRESSIVE` / `RUNTIME_FAILOVER` /
`HUMAN_ESCALATION`); the decision layer records the kind and bound — the *timing/backoff* of a
retry belongs to the actor that performs it, not to this decision.

## 4. Aggregation precedence (`RecoveryEvaluator`)

Deterministic, highest wins (`DECISION_PRECEDENCE`):

1. **Complete** — a Passed run needs no recovery.
2. **Await Approval** — governance / inconclusive is never bypassed (INV-22).
3. **Abort** — the policy marks this category fatal.
4. **Resume** — progress preservation outranks a full re-run (doc 19 *Progress Preservation*).
5. **Retry** — retryable with budget remaining.
6. **Escalate** — the safe floor: a failure is never silently dropped.

The determination also records the *derivation*: the deciding rule, `retry_eligible` /
`resumable` flags (whether those rules were applicable, regardless of the winner), the
required next actions, per-decision recommendations, and a one-line-per-rule `reasoning_trace`
(INV-31).

## 5. Explainability (INV-31)

Every plan carries a `reasoning_trace` (`rule_id: outcome [-> proposed] — rationale`), the
`failure_category`, `required_actions`, and `recommendations`. The four doc-19 "why" questions
(what failed / why / why this recovery / what state resumes) are answerable from the Plan
alone.

## 6. Extensibility

New rules are new `RecoveryRule` implementations added to `DEFAULT_RULES` (or a custom tuple
passed to `RecoveryEngine`) with a slot in `DECISION_PRECEDENCE`; `RecoveryPolicy` toggles
categories and budgets. Doc-19's richer strategies (Rollback / Switch Runtime / Request
Context) and Replan are reserved for a later program — they are new rules + decisions, no
engine change.
