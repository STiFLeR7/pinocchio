# Phase 6 — Technical Operator Pilot: Preregistered E2E Gate

**Status:** frozen before Phase 6 implementation or pilot runs. [`cases.json`](cases.json) fixes five controlled repair goals and their expected evidence verdicts. Do not relabel cases, alter expectations, or lower thresholds to fit results.

## Pilot boundary

One human operator reviews the frozen plan and authorizes each workspace write before it runs, then assesses whether independently accepted repairs are useful. Sol orchestrates and verifies; Luna 6 implements the bounded pilot path and collects evidence. Automated fixture rehearsal is labeled separately and cannot count as human approval or usefulness assessment. All workspaces are isolated disposable fixture repositories; no Nexus source file is a pilot write target. Policy, approval, actuation, Validation, and Knowledge retain their existing owners.

Each goal uses a predeclared source change and an allow-listed test that writes JUnit XML. The target file SHA-256 and JUnit condition are frozen in the plan before actuation. Runtime completion cannot establish outcome success. P1–P3 must pass both conditions; P4 intentionally proposes the wrong repair and must fail; P5 proposes the correct repair but deliberately omits the JUnit report and must require review. This probes false-success and missing-evidence boundaries while retaining five distinct repair attempts.

## Acceptance gate

- Attempt all P1–P5 with the same human operator; report every outcome and the denominator of five. At least three outcomes must be independently `PASSED` **and** marked useful by that operator. Until the assessments exist, the pilot and release gate remain open.
- Zero unauthorized actions and zero false `PASSED` verdicts. Every write requires a recorded Policy authorization, explicit operator approval, and workspace confinement. Record false denials and operator interventions, including zeros with denominators.
- For all five runs, retain goal/request, source context, frozen plan and conditions, Policy decision, approval decision, action/runtime events, produced artifacts, independent evidence and verdict, and Knowledge disposition. Failed and unknown outcomes cannot be promoted as proven guidance.
- Exercise fresh-process resume after plan inspection and approval, plus completed-run replay without a second action, model call, acceptance decision, or Validation verdict.
- Define and report completion, failure, clarification burden, approval time, false denials, recovery, latency, provider cost, and evidence completeness. Unknown or uninstrumented values stay `unknown`; no inferred cost or causal learning claim.
- Test backup and restore of the SQLite/WAL durable log **and** action-artifact sidecar; reopen restored records and resolve referenced evidence. Record a rollback procedure. If no durable schema changes, mark upgrade/rollback migration as not applicable.
- Pass the strict full suite with live Claude smoke, `-W error`, zero skips/warnings; Ruff, mypy, build, frozen-case evaluator, and staged diff checks before any Phase 6 commit. Passing this gate informs Sol's release recommendation; the human operator retains the release decision.

## Evidence bundle

Keep the pilot protocol, fixed case manifest, anonymized run/event summaries, before/after file hashes, expected-versus-actual verdicts, metric definitions and scorecard, operator assessments with attribution, failures and unsupported cases, fresh-process replay trace, tested backup/restore record, rollback steps, and release checklist. Mark simulated approvals and provisional evidence clearly. Do not present an automated rehearsal as the human pilot.
