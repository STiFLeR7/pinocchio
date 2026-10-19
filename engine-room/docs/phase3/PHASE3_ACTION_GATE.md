# Phase 3 — Constrained Repository Actions: Preregistered Gate

**Status:** preregistered acceptance contract; freeze before implementation.  
**Scope:** prove one Nexus-owned repository action path with external policy and human approval decisions.  
**Machine-readable cases:** [`cases.json`](cases.json)

## Acceptance boundary

The operator supplies a structured action and explicit workspace together with the Phase 2 request. The immutable `action.requested` event is the source of the complete action input and digest. A `Reference(target_type="action_request", identifier=<action ID>)` travels in the planned work item's existing `inputs` field, then in `WorkPackage.inputs`; the frozen plan binds that reference to a session and node. Planning schema and frozen core contracts are not presumed to change.

Before a side effect, the coordinator resolves that reference from the durable event log, verifies the input digest, and asks Policy to evaluate the exact action, plan/node, workspace, and input digest. A write requires an actual Approval Exchange `APPROVED` event for that plan session and node, bound to the same action reference/digest. `requires_approval` and strategy hints alone do not authorize a write. Policy denial/failure or missing/mismatched approval prevents the action from starting. The action boundary independently verifies the workspace, rejects traversal and every symlink path component, checks any test command against an explicit allow-list, and records start/result facts and artifact references.

Replay reads the original action input through the frozen plan's reference and the durable event log. A completed action reconstructs its result without dispatching again. A start without a terminal action result means the outcome is indeterminate: restart halts for operator reconciliation and never silently repeats the action. The coordinator must detect this before calling the Actuator; its current node-start replay behavior alone is not sufficient to establish action-level no-repeat. Tests must not infer successful completion from an adapter or provider's self-report.

This contract covers only actions dispatched through the Nexus-owned constrained action boundary. Claude Code CLI, Gemini CLI, and other provider runtimes remain opaque: this gate makes no claim that Nexus sees or governs tool calls performed internally by those providers.

## Frozen cases and pass thresholds

The cases in `cases.json` are frozen before implementation. Do not edit their IDs, inputs, or required outcomes to fit implementation behavior; additions require separate cases and results. All 14 cases must pass.

- A1 declares `approval_hint=AUTOMATIC` and proves a write still waits for a real human Approval Exchange decision: there is no `action.started` before approval. After approval, only the explicitly allowed target changes; policy, approval, diff, and result are inspectable.
- A2 is explicitly a human-denied write. A3–A6 have no action-start event for traversal, symlink, unlisted-command, and workspace-mismatch rejection; all leave every fixture file byte-identical.
- A7 is read-only and leaves every fixture file byte-identical.
- A8 records cancellation and verifies no later action starts; bytes are checked against the declared cancellation semantics.
- A9 proves a completed action executes exactly once across process restart.
- A10 proves an action with `started` but no terminal event becomes indeterminate and is never redispatched automatically.
- A11 links request, actor, goal, plan, node, exact action reference/digest, policy, approval, action start/result, and artifacts using stable IDs.
- A12 proves the CLI uses the opaque Nexus action identity and does not invoke an arbitrary executable or expose a provider CLI as governed.
- A13 proves the named allow-listed test action runs with fixed argv, no shell, recorded exit status, and event lineage.
- A14 proves Policy DENY remains authoritative even when matching human approval exists: no action start and byte identity.

No denied action may change bytes. No read-only action may change bytes. No restart may dispatch an action already recorded complete. Any action whose state is indeterminate must halt for reconciliation before Actuator dispatch. Any Policy DENY blocks action start even if approval exists. Policy and approval must match the same action input digest and plan/node. Final strict full-suite validation must run with warnings treated as errors, zero skips, and zero warnings; the opt-in Claude smoke remains separately identified and must not be silently counted as run. Ruff, mypy, and build gates must also pass.

## Fixture and evidence contract

Use an isolated temporary fixture repository with this layout (tests create it at runtime; no checked-in user workspace is used):

```text
fixture/
  workspace/
    README.md             # allowed write/read target
    src/app.py            # second in-scope file for unchanged-byte checks
    tests/test_app.py     # target of the one allow-listed test command
    escape-link           # symlink to ../outside/secret.txt
  outside/
    secret.txt            # sentinel; must remain byte-identical
```

The symlink case must create and exercise a real symlink; it must not skip. Before and after each case, record SHA-256 for every regular file under both `workspace/` and `outside/`, plus the relative path inventory. Preserve the approved write's unified diff and its target before/after hashes. Record symlink target and resolved path in the denial evidence without following it as an authorized target.

For each run, retain a sanitized, machine-readable event trace with stable event IDs, event types, producer, correlation, and only safe payload fields needed to verify lineage. It must show the original action input/digest, plan reference, session/node binding, policy result, approval state, action start/result, cancellation or indeterminate state where relevant, and artifact/diff references. Do not include secrets or environment values.

Run A1, A2, A7, A8, A9, A10, A11, A12, and A13 through the operator-facing path. At minimum, A9 and A10 must cross a real process boundary: submit/plan and persist in process one, close it, then restart with a fresh process and the same durable store. A9 must show one side effect total. A10 must simulate the post-side-effect/pre-completion crash window and show a reconciliation halt with no second side effect. A12 and A13 must inspect CLI output and process invocation evidence. Other cases may use the same operator path or a narrower integration path when that path is needed to isolate the security boundary.

The evidence bundle must include the frozen cases, fixture inventory, before/after hash manifests, approved diff, denial proofs, cancellation trace, separate-process replay traces, event-lineage export, opaque-boundary note, and an evaluation report listing every case's observed result, pass/fail, thresholds, and failures. A passing count without per-case results is insufficient.
