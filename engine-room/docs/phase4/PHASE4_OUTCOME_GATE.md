# Phase 4 — Independent Outcome Evidence: Preregistered Gate

**Status:** frozen before Phase 4 implementation. The machine-readable cases are in [`cases.json`](cases.json). These IDs, inputs, expected verdicts, and thresholds must not be changed to fit an implementation.

## Acceptance boundary

The operator supplies testable conditions in the existing work item's `completion_criteria` before actuation; Planning freezes them in the `WorkPackage`. A raw request without a confirmed, testable condition cannot receive an outcome `PASSED` verdict. Runtime completion and exit status are process facts, not outcome acceptance.

This gate uses only two finite condition types: a workspace-relative file SHA-256 equality check and a JUnit XML result check tied to a named, allow-listed `run_test` action. Validation reads the selected file or JUnit report independently, refuses traversal or symlink escape, checks the source and artifact hash where an action artifact reference exists, and records the observation's source, digest, lineage, and limitation. A JUnit report's assertion counts are stronger than the wrapper process's exit code; the report is still only evidence about the tests that ran. No LLM self-assessment, generic semantic judge, or provider-internal tool call counts as outcome evidence.

The verdict precedence is fixed: conflicting valid evidence for the same condition yields `REQUIRES_REVIEW`; absent, invalid, or unreadable required evidence yields `REQUIRES_REVIEW`; all satisfied yields `PASSED`; all evaluated conditions violated yields `FAILED`; a mix of satisfied and violated conditions yields `PARTIAL`. A violated test condition remains `FAILED` when the action or runtime exits zero. Existing v2 validation rules remain applicable to process facts; they cannot promote an unmet explicit condition to `PASSED`.

## Frozen five-case fixture

Each case uses an isolated workspace, a real named `run_test` action where specified, and a durable SQLite event store. The test fixture writes a deterministic JUnit XML report; its wrapper deliberately exits zero in E2 to test the trust boundary. `README.md` supplies file-hash checks in E1 and E4. Cases are executed through the operator-to-Validation path, with condition records frozen before the action starts. Missing and conflicting evidence are induced after registration, never by changing the expected verdict.

| ID | Condition/evidence | Expected verdict |
| --- | --- | --- |
| E1 | Required file digest matches; named test JUnit report has no failures or errors. | `PASSED` |
| E2 | Named test's JUnit report records one assertion failure while its wrapper and runtime report exit code zero. | `FAILED` |
| E3 | A required JUnit report is absent or its referenced digest cannot be verified. | `REQUIRES_REVIEW` |
| E4 | File digest matches; independently read JUnit report records a failed required test. | `PARTIAL` |
| E5 | Two valid, separately referenced JUnit reports for the same registered test condition disagree on pass/fail. | `REQUIRES_REVIEW` |

## Pass thresholds

All five cases must match their frozen verdicts, with zero false passes. Every `PASSED` report must cite sufficient evidence for every registered condition. Every other report must name the failed, missing, or conflicting condition and cite available sources. Every observed external file or action artifact must have a verified digest and bounded workspace path. The operator-facing result must distinguish runtime completion from outcome acceptance.

For each case, close process one, reopen the same durable store in a fresh process, and reconstruct the same report, condition digest, evidence references, and verdict without runtime dispatch, external evidence collection, or workspace/artifact reads. The replay must not append a second validation decision. Retain acceptance-condition records, source/hash manifest, evidence bundle, expected-versus-actual verdict table, process and event trace, fresh-process replay proof, and limitations by evidence class. The strict full suite must pass with warnings as errors, live Claude smoke enabled, zero skips/warnings, followed by Ruff, mypy, build, and a clean staged diff check before commit. Passing this phase grants no autonomous write authority.
