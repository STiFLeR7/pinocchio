# Pattern Analysis — implementation

Milestone 2. Analyzers are deterministic, evidence-backed, and explainable — **pure
aggregation, no statistical learning, no heuristics, no AI** (doc 26 *Evidence First*). Each
analyzer is a pure function of the collected `OperationalHistory` and emits
`OperationalPattern`s that reference the episodes they were derived from (INV-12).

---

## 1. The operational episode (collection)

The collector correlates the three per-execution outputs into one `OperationalEpisode` per
**session** (`ExecutionResult` / `ValidationReport` / `RecoveryPlan` share the session
identity). The episode is a *read-only projection* — it references the underlying objects by id
and copies only the small, deterministic descriptors the analyzers aggregate over (verdict,
recovery decision, failure category, retry basis, runtime, exit status, metrics). Sessions are
ordered by first appearance across the inputs, so the history is deterministic. Collected data
is never modified.

## 2. The supported analyses

| Analyzer | Pattern kind | Aggregation |
|---|---|---|
| `RepeatedFailureAnalyzer` | `repeated_failure` | failing episodes grouped by failure category |
| `RepeatedSuccessAnalyzer` | `repeated_success` | passing episodes grouped by runtime |
| `RetryFrequencyAnalyzer` | `retry_frequency` | count + rate of episodes routed to Retry |
| `ValidationOutcomeAnalyzer` | `validation_outcome` | episodes grouped by validation verdict |
| `RecoveryDecisionAnalyzer` | `recovery_decision` | episodes grouped by recovery decision |
| `RuntimeUtilizationAnalyzer` | `runtime_utilization` | episodes grouped by runtime |
| `ExecutionDurationAnalyzer` | `execution_duration` | aggregate (count/total/min/max/mean) of `duration_ms` |
| `BottleneckAnalyzer` | `bottleneck` | the dominant friction category across failures/friction decisions |

Each analyzer returns *no pattern* when its dimension is absent (e.g. no failures → no
`repeated_failure`; no `duration_ms` samples → no `execution_duration`; no friction → no
`bottleneck`), so the report only ever asserts what the evidence supports.

## 3. Determinism guarantees

- **Grouping** preserves first-seen order over the already-ordered episode sequence.
- **Ids** are pure functions of `(scope, kind, ordinal)`.
- **Bottleneck tie-breaking** is deterministic: the highest-count friction category, ties
  broken by first-seen order (`max` over a first-seen-ordered list).
- No clock, no randomness, no learned parameters — identical history ⇒ identical patterns
  (proven by the engine and E2E determinism tests).

## 4. Evidence model & confidence

- Every `OperationalPattern` carries `evidence_refs` — the **most specific persisted reference**
  for each contributing episode (recovery plan > validation report > execution result), so a
  finding is traceable back through the pipeline to its source events.
- **Confidence is derived deterministically from the repetition count** (doc 26 levels), never
  learned: `1 → Experimental`, `2 → Observed`, `3-4 → Validated`, `≥5 → Proven`. A finding is
  *confirmed* when it repeats at least twice. This lets Knowledge prioritise higher-confidence
  reflections (doc 26).

## 5. Extensibility

New analyses are new `OperationalAnalyzer` implementations added to `DEFAULT_ANALYZERS` (or a
custom tuple passed to `ReflectionEngine`). Any analyzer returning `OperationalPattern`s with a
new `PatternKind` composes without an engine change; making its confirmed patterns *actionable*
(a Knowledge Candidate) is one entry in the synthesizer's `_ACTIONABLE` map.
