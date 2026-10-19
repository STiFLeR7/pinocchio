# Phase 6 release review

Run: `20260930-operator-pilot-01`. The [frozen gate](PHASE6_PILOT_GATE.md) and [cases](cases.json) were recorded before implementation or pilot execution. The controlled pilot used one approved operator identity and five separate disposable workspaces outside the Nexus checkout. This is a technical operator pilot, not a production reliability claim.

| Case | Independent edit / test verdict | Knowledge disposition | Operator usefulness |
| --- | --- | --- | --- |
| P1 addition | passed / passed | accepted | useful |
| P2 normalization | passed / passed | accepted | useful |
| P3 clamp | passed / passed | accepted | useful |
| P4 deliberately wrong title repair | failed / failed | rejected | not useful |
| P5 slug repair without required JUnit report | passed / requires review | none | not useful |

The [pilot scorecard](evidence/pilot/20260930-operator-pilot-01/scorecard.json) contains the event traces, file hashes, approval facts, verdicts, and replay comparisons. The operator's five assessments and [false-denial response](evidence/pilot/20260930-operator-pilot-01/operator_feedback.json) are recorded separately. All five runs have complete lineage; each has two policy-authorized action starts and one operator-approved write. No unauthorized action, false passed verdict, or replay duplication was observed; the operator reported zero false denials. Completion is 3/5, and all three completed repairs were rated useful. One case failed and one requires review. Clarification count is 0/5. The harness added a software-domain prefix to all five requests to satisfy the current Intent route; those five interventions are recorded. Human review duration and provider cost are unknown, not inferred from machine timestamps.

The [actual pilot backup and restore record](evidence/pilot/20260930-operator-pilot-01/backup_restore.json) verifies SQLite online backup, action-artifact sidecar restore, nine artifact hashes, same-path replay, and retained rollback copies. The [automated rehearsal](evidence/rehearsal/automated_rehearsal.json) exercised the same recovery path separately with simulated approval and contributes no human usefulness rating. This phase makes no durable schema change, so schema migration and rollback are not applicable.

The live-Claude strict suite passed 3,261 tests with `-W error`, zero skips and zero warnings. Ruff check, Ruff format check on Phase 6 files, mypy on Phase 6 Python files, and `uv build` passed. A whole-repository Ruff format check reports 55 previously existing files outside Phase 6; those files were not changed for this pilot.

**Technical pilot gate: passed.** All five operator ratings are present, all frozen scorecard checks pass, and the three independently passed repairs are rated useful. Sol recommended a limited v2.5 release review, and the operator subsequently requested the v2.5.0 stable release with the scope limits recorded here. These five disposable fixtures do not test arbitrary real repositories or sustained operation, and the Intent prefix is a measured intervention.

For the consolidated release scope, see the [v2.5.0 release report](../releases/V2_5_RELEASE_REPORT.md).
