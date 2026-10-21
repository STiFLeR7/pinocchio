# Documentation Phase 4 Report — Production Examples & Reference Workflows

**Status: Complete.** No implementation change was required or made — every example composes existing,
released, already-tested composition roots and public APIs. `git diff --stat` (see §4) confirms the
only non-`examples/`, non-`docs/` change is one corrected section of the root `README.md` (its
"Examples" section previously stated none existed — now stale, given this phase's own deliverable).

---

## 1. Example Library Structure

`examples/` was created with the exact ten-directory structure the governing prompt suggested, each
holding one `run.py` plus one `README.md`:

```
examples/
    README.md                    <- library-wide index, prerequisites, learning progression
    01-hello-nexus/
    02-first-pipeline/
    03-policy-governance/
    04-runtime-selection/
    05-memory/
    06-scheduler/
    07-approval-exchange/
    08-replay/
    09-recovery/
    10-autonomous-workflow/
```

Before writing any example, the exact API surface each would need was verified directly against
source (not assumed from prior session knowledge) — `SpineRequest`/`spine_reference_request`,
`build_constitutional_pipeline`'s `adapter_factory`/`knowledge_repositories` seams,
`ApprovalExchange.publish`/`approve`/`deny`, `Scheduler.schedule_goal`/`ScheduleTrigger`,
`PolicyEngine.evaluate`/`DecisionRequest`, `ShellRuntimeAdapter`/`StubShellInvoker`,
`KnowledgeRepositories.items.get`, and the real field names of `SpineRun`, `SessionSummary`, and the
`Knowledge` domain object. This grounding step caught several would-be invented-API mistakes before
any example was written (see §3's per-example notes on what the real fields turned out to be, e.g.
`SessionSummary.status`/`stages_completed` rather than an invented `is_complete`).

`examples/README.md` documents the learning progression (§3) and states the one property that makes
this whole library trustworthy: **every example was executed directly, not just written to look
correct** — see §4 for the validation record.

---

## 2. Examples Created

All ten, each backed by real, cited APIs, none of them requiring a new fixture, test helper, or
`nexus_*` package change:

| # | Example | Capability | Key real API used |
|---|---|---|---|
| 01 | Hello Nexus | Smallest complete run | `build_infrastructure`, `build_constitutional_pipeline`, `spine_reference_request` |
| 02 | First Pipeline | All 9 stages + Operations plane | + `build_approval_exchange`, `build_operations`, `OperationsService.session_lookup` |
| 03 | Policy Governance | Fail-closed, explainable governance | `build_policy`, `DecisionRequest`, `PolicyEngine.evaluate`, the real seeded defaults (`GLOBAL_COMMAND_BLACKLIST`) |
| 04 | Runtime Selection | Pluggable runtime adapters | `build_constitutional_pipeline(..., adapter_factory=...)`, `ShellRuntimeAdapter`, `StubShellInvoker` |
| 05 | Memory (Knowledge) | Durable memory, read back by identity | `build_knowledge_repositories`, `KnowledgeRepositories.items.get` |
| 06 | Scheduler | One-time, recurring, restart | `Scheduler.schedule_goal`, `ScheduleTrigger.one_time`/`.interval`, a genuine rebuild-from-durable-file restart |
| 07 | Approval Exchange | Gated pause/resume | `ApprovalExchange.publish`/`.approve`/`.explanation` |
| 08 | Replay | Exact reconstruction from the log alone | `reconstruct_pipeline_session`, discarding all prior in-memory objects before reading back |
| 09 | Recovery | Deterministic outcome from failure | `SpineRequest(fail=True)` — the same seam RC1/RC2's own regression tests use |
| 10 | Autonomous Workflow | Full no-human-in-the-loop showcase | `AutonomyMode.FULLY_AUTOMATIC` + `ScheduleTrigger.immediate()`, composing 02/03/06/07/09's mechanisms |

Every example includes all seven documentation elements the prompt specified: purpose, prerequisites,
architecture (a Mermaid diagram), code walkthrough, expected output (captured from a real run, not
composed), troubleshooting, and a pointer to the next example.

---

## 3. Learning Progression

Ordered so each example only depends on a concept the previous one introduced (full rationale and
table in `examples/README.md`): 01 → 02 → {03, 04, 05, 06, 07} → 08 → 09 → 10. Three real mistakes
were caught and fixed *during* this ordering-and-verification process, each worth recording because
they're the kind of error an unverified example would have silently shipped:

1. **`SessionSummary` has no `is_complete` field** (example 02) — the real fields are `status`,
   `current_stage`, `stages_completed`, `pending_approvals`, `is_paused`
   (`nexus_operations/model.py`). Caught by running the script, not by reading the field name
   correctly the first time.
2. **`Knowledge` has no `subject_key`/`content` fields** (example 05) — the real contract fields are
   `type`, `understanding`, `confidence`, `freshness`, `evidence_refs`
   (`nexus_core/domain/knowledge.py`). Same failure mode: an assumed field name that doesn't exist.
3. **Rebuilding the whole platform on every scheduler tick, not just at the genuine restart**
   (example 06) — an early draft called `_boot()` fresh for the T1 tick as well as the T2 restart,
   which produced a real `DuplicateEventError` (a knowledge-acceptance event colliding under a
   different injected clock value on rebuild). This was a bug in the *example's own logic* — a real
   process would never rebuild between two ticks it makes itself — not a platform defect. Fixed by
   reusing the same `scheduler` object for consecutive ticks within one "process," and only rebuilding
   for the actual restart step.

Every one of these was caught by the "examples run" validation discipline itself (§4) — none would
have been caught by writing plausible-looking code and reviewing it by eye.

---

## 4. Validation Results

- **Every example runs, from a clean state, right now**: all ten scripts were executed directly via
  `.venv/Scripts/python.exe examples/<N>/run.py` — not merely reviewed — with zero modification needed
  after the fixes in §3. Re-run again immediately before writing this report, fresh, all ten: **10/10
  PASS**.
- **Determinism verified**: three representative examples (01, 05, 09) were run twice in a row and
  their output byte-diffed — identical both times. This matters because every README's "Expected
  Output" section is the literal captured output of a real run, not a hand-composed approximation —
  a reader who runs an example should see exactly what's documented.
- **Imports resolve**: every `import` in every `run.py` is a real, existing symbol — verified by the
  scripts actually executing (an invented or misspelled import fails immediately at the top of the
  file, before any output).
- **Links resolve**: every relative link across `examples/README.md`, all ten per-example `README.md`
  files, and the root `README.md`'s corrected Examples section was checked against the filesystem
  (with anchor fragments like `#prerequisites-all-examples` correctly stripped before the check) — all
  resolve.
- **Mermaid diagrams render**: all 12 Mermaid blocks (one per example's architecture diagram, plus the
  two in the root README) checked for bracket balance — all balanced.
- **No pseudo-code presented as runnable**: every code block in every "Code Walkthrough" section is a
  literal excerpt from the corresponding `run.py`, not paraphrased or simplified into something that
  wouldn't actually run.
- **No obsolete APIs**: every symbol used was verified against the current `v2.0.0` source directly
  during this phase, not recalled from an earlier session or an outside assumption.
- **Scope discipline**: `git diff --stat` / `git status --short` show only `examples/` (all new),
  `docs/DOCUMENTATION_PHASE4_REPORT.md` (new), and one corrected section of the root `README.md` — no
  `nexus_*/` package, test, or CI file was touched.

---

## 5. Remaining Work

Explicitly not started this phase, per its own closing instruction ("do not begin tutorials,
benchmarks, ADR remediation, release cadence documentation, or contributor process improvements"):

1. **Tutorial series** (master plan §8) — now genuinely unblocked, since it was explicitly sequenced
   to depend on the example library existing first. Not started this phase.
2. **Benchmarks page** (master plan §6) — unchanged from Phase 3; real numbers exist, publishing them
   as a standing page remains future work.
3. **ADR-005/006 gap** (master plan §1.7/§5) — unchanged; still documented, still unresolved.
4. **Release-cadence documentation** and **contributor-process improvements** — both explicitly
   excluded from this phase by name.
5. **`docs/concepts/` and `docs/guides/`** (Phase 3 §4's carried-forward gap) — still no real content
   behind either; unaffected by this phase's work.
6. One small, genuinely optional follow-up this phase noticed but did not act on: `examples/README.md`
   and the per-example READMEs could eventually link to a tutorial once one exists for each capability,
   the way the root README's Documentation Map already anticipates — not needed until §5.1 above starts.

Per the governing prompt: stopping here.
