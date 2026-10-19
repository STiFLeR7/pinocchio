# Cross-Runtime Compatibility, Selection & Validation — Implementation

This is the heart of Capability Program 2: proving one governed workflow runs across Claude,
Gemini, and Shell by **adapter substitution alone** (Milestones 4–6). All three are driven by
`nexus_runtime_adapters` over the *existing* `nexus_workflows` pipeline — no engine redesign.

## Milestone 4 — cross-runtime compatibility

`CrossRuntimeRunner.run_on(identity, request)` builds a standard `Pipeline` and drives the
existing `WorkflowCoordinator` with an adapter factory that resolves `identity` from the
`AdapterRegistry`. The **only** thing that changes between runtimes is that factory — Planning,
Orchestration, Harness, Runtime Manager, and Execution are byte-for-byte the same code path.

The one enabling change to the coordinator is a single injected seam:

```python
WorkflowCoordinator(pipeline, adapter_factory=lambda req: registry.create(identity, ...))
```

`adapter_factory` defaults to the Claude construction, so the existing reference workflow and its
byte-identical determinism tests are unchanged. `run_matrix(request)` runs the same request on
every runtime and returns the tagged outcomes. `test_same_work_packages_execute_on_every_runtime`
asserts the identical two Work Packages complete on all three.

## Milestone 5 — deterministic selection

`select_runtime(registry, required_capability_refs, runtime_policy)` (`selection.py`) chooses one
runtime as a **pure function** of its inputs — required capabilities, declared capabilities, and
declarative policy. It invents no algorithm: it projects the adapter registry's descriptors into
the Runtime Manager's own `RUNTIME`-category `RuntimeRegistry` and runs the existing
`RuntimeSelector` funnel (`match → health → policy → choose`), fail-closed on an empty survivor
set. No heuristics, no AI, no clock, no randomness.

| Inputs | Chosen |
|---|---|
| `code_generation`, no policy | `claude-code` (lowest identity, total tiebreak) |
| `code_generation`, `preferred_runtimes=("gemini-cli",)` | `gemini-cli` |
| `code_generation`, `allowed_runtimes=("shell",)` | `shell` |
| `command_execution`, no policy | `shell` (the only advertiser) |
| `time_travel` | **`CapabilityMismatchError`** (fail-closed) |

## Milestone 6 — cross-runtime validation

`governance_signature(run)` extracts the part of a run that governance guarantees **regardless of
the runtime**:

```python
GovernanceSignature(
    work_package_ids, execution_outcomes, validation_decisions,
    recovery_decisions, governance_event_types, reflection_candidate_count,
)
```

`governance_event_types` is the run's event-type sequence with the three runtime-*variable* types
removed — `runtime.output`, `runtime.progress`, `runtime.artifact_emitted`. What remains is the
governance skeleton: every other engine's events plus the runtime lifecycle
(`session_created → candidates_resolved → capabilities_matched → allocated → prepared → ready →
started → completed/failed → destroyed`). This skeleton is **identical** across Claude, Gemini,
and Shell.

`test_governance_is_identical_across_runtimes` asserts the full signature is equal for all three
runtimes; `test_failure_flow_is_identical_across_runtimes` asserts the same for the `fail=True`
path (`failed → failed → retry` everywhere). The differences are confined to what the mission
allows — *only runtime-specific artifacts*:

| Runtime | Produced artifact | Total events (happy path) |
|---|---|---|
| `claude-code` | `<wp>-main.py` | 111 |
| `gemini-cli` | `<wp>-summary.md` | 111 |
| `shell` | `<wp>-output.txt` | 107 |

The event *count* differs (the shell emits no progress and a different output count), but every one
of those differing events is in the excluded runtime-variable set, so **governance is identical**.
Each runtime is also byte-identical across repeat runs
(`test_each_runtime_is_byte_identical_across_repeat_runs`).

## Governance verification summary

* **identical orchestration** — same Work Packages, same Plan/Execution Graph, same harness
  requests (the non-runtime event types are identical across runtimes).
* **identical governance** — same validation decisions, same recovery decisions, same reflection
  candidate count.
* **identical event model** — same `runtime.*` lifecycle skeleton and same event vocabulary.
* **identical recovery flow** — `complete` on success, `retry` on failure, on every runtime.
* **only runtime-specific artifacts differ** — the produced file id and the streamed output text.
