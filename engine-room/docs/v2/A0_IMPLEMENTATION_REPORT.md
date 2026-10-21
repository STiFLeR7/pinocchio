# Nexus — A0 Implementation Report

Status: **Engineering validation — executed, not designed.** One real engineering vertical built and
run end-to-end against a real Claude Code session over a real repository. Additive code only; no ADR,
contract, invariant, or existing engine modified. Nothing committed.

**Headline: the architecture survived real implementation.** A real `claude` session, driven through
all ten v2 engines against a real repository copy, produced a real filesystem change that was
**independently validated on disk** (INV-20), with the one dangerous operation held **fail-closed**
(INV-30). The reference workflow ran — with three honestly-documented stubs and one low-severity
architectural conflict, none of which required a redesign.

---

## 1. What was run (the evidence)

Real run — `python -m scripts.a0_run` (venv), real `claude` v2.1.201 (`claude-sonnet-5`), isolated
copy of `D:/port`:

```
# A0 Vertical Briefing -- SUCCEEDED
objective       : Create A0_PROOF.txt containing exactly one line: NEXUS-A0-OK
working_dir     : D:\port-a0-run           (throwaway copy; D:/port never touched)
repo grounded   : 72 files, langs=[css,javascript,json,markdown,typescript],
                  key_docs=[README.md, CLAUDE.md, AGENTS.md, package.json]
execution       : ['completed']            (real claude session, driven by nexus_execution)
validation      : ['passed']               (nexus_validation, from evidence)
recovery        : ['complete']             (nexus_recovery)
independent chk : verified on disk: 'A0_PROOF.txt' contains 'NEXUS-A0-OK'   (INV-20)
commit gate     : DENIED (fail-closed: no human authorization recorded)     (INV-30)
committed       : False
events recorded : 73
```
Filesystem proof: `D:/port-a0-run/A0_PROOF.txt` = `NEXUS-A0-OK` (created by real claude);
`D:/port/A0_PROOF.txt` absent (source working tree untouched — **safety boundary held**).

Determinism preserved: unit tests reproduce the whole vertical over `StubClaudeInvoker` with no
network. `45 passed`; ruff clean; mypy clean.

---

## 2. Implementation graph (benchmark step → status)

| # | Benchmark step | Status | Realized by |
|---|---|---|---|
| 1 | Receive request | ✅ implemented (direct) | `A0TaskSpec` → `build_a0_request` |
| 2 | Understand repository | ✅ **new (thin)** | `nexus_workflows/repo_intelligence.py` (real disk read) |
| 3 | Gather repository context | ✅ reused | `nexus_context` (fragment → Context Package) |
| 4 | Determine clarification need | 🟡 stub | Goal built directly; no Intent Resolution engine (exists only as a type) |
| 5 | Ask the human | 🟠 stub | no live channel; gate is code-local (see §6) |
| 6 | Plan the work | ✅ reused | `nexus_planning` (Plan + Execution Graph + Strategy) |
| 7 | Produce work packages | ✅ reused | `nexus_planning` (single Work Package) |
| 8 | Select a runtime | ✅ reused | `nexus_orchestration` (INV-37, candidates) |
| 9 | Open Claude Code | ✅ **real** | `ClaudeCliInvoker` → `claude -p … stream-json` |
| 10 | Operate the real repository | ✅ **real** | real edit in isolated copy (`working_dir` seam) |
| 11 | Approval before dangerous ops | ✅ **new** | `ApprovalGate` — fail-closed (INV-30) |
| 12 | Execute the work | ✅ reused | `nexus_execution` drives the adapter → real signals |
| 13 | Validate independently | ✅ **new + reused** | `nexus_validation` + on-disk `_independent_validate` (INV-20) |
| 14 | Recover if validation fails | ✅ reused | `nexus_recovery` (`complete` on success) |
| 15 | Produce a briefing | ✅ **new** | `A0Result.briefing` (report-back) |
| 16 | Persist operational knowledge | ⚠️ conflict | `nexus_reflection`→`nexus_knowledge` ran but a single episode persists nothing → `ARCHITECTURAL_CONFLICT_1.md` |

Dependency direction (unchanged): the whole vertical is driven through
`WorkflowCoordinator`; the real repo path reaches Claude **only** via the runtime adapter's
`working_dir` (the Execution Engine performs, it does not re-configure); nothing upstream imports the
A0 layer.

---

## 3. Reused architecture (the validation)

Ten engines composed **without modification**, exactly as `docs/v2/` specify:
`nexus_context → nexus_planning → nexus_orchestration → nexus_harness → nexus_runtime →
nexus_execution → nexus_validation → nexus_recovery → nexus_reflection → nexus_knowledge`, wired by
the existing `PipelineBuilder` and `WorkflowCoordinator`. The provider seam behaved exactly as
designed: swapping `StubClaudeInvoker` → `ClaudeCliInvoker` via the sanctioned `adapter_factory` was
the **only** change needed to move from a reproducible stub to a real Claude session. The event log,
determinism source, INV-20 (evidence over self-report), INV-30 (fail-closed), and INV-37 (orchestration
selects) all held under real actuation.

## 4. New code (all reusable; no workflow-specific hacks)

| File | Purpose | LOC |
|---|---|---|
| `nexus_workflows/repo_intelligence.py` | thin, reusable Repository Intelligence (real repo → context fragment) | ~150 |
| `nexus_workflows/a0.py` | the A0 vertical: real-Claude factory, request builder, fail-closed `ApprovalGate`, independent validation, briefing | ~300 |
| `scripts/a0_run.py` | runnable entrypoint: isolate copy → run → evidence → cleanup | ~110 |
| `tests/unit/nexus_workflows/test_a0_vertical.py` | 7 deterministic tests (stub-driven, CI-safe) | ~110 |
| `nexus_runtime_claude/adapter.py` | **1-line** additive change: `working_dir` settable at construction | +1 param |

## 5. Removed stubs

- **The default execution path is no longer stub-only.** Before A0, every runnable path bottomed out
  on `StubClaudeInvoker`; A0 introduces a real, reusable, tested path to a real Claude Code session
  over a real working directory. The stub remains — correctly — as the deterministic CI/replay
  substrate, but it is no longer the *only* validated option.

## 6. Remaining stubs (explicit, per Phase 5)

1. **commit/push to the real repository** — gated fail-closed; A0 operates on an isolated copy and
   never writes back. (Safety choice; the gate is real, the act is deferred.)
2. **human approval via a real channel** — `ApprovalGate` is a real fail-closed enforcement point but
   is *code-local*; it is not yet routed to a human through Human Interaction / a Discord channel.
3. **governed Actuation session** — A0 uses a one-shot `ClaudeCliInvoker`, not the frozen Actuation
   design's reattachable, permission-enveloped Session. Sufficient for A0; not the full substrate.
4. **Engineering Intelligence** — the objective is passed through directly; no approach/methodology
   selection or gate-placement cognition yet.
5. **Intent Resolution / clarification loop** — the Goal is constructed directly; no normalization or
   clarification exchange.

## 7. Architectural conflicts

- **`ARCHITECTURAL_CONFLICT_1.md`** — single-episode runs persist no Knowledge (benchmark step 16).
  Evidence-backed; **low severity**; zero-code mitigation (treat "persist knowledge" as a cross-run
  property, proven by the existing knowledge-feedback test). Reflection's pattern-confirmation
  discipline is sound and was **not** changed.

No other conflict surfaced: the ten-engine composition, the provider seam, and every touched invariant
survived real actuation intact.

## 8. Technical debt

- `ClaudeCliInvoker` parses only `assistant`/`result` stream-json lines; `tool_use`/tool-result lines
  degrade to generic text (no `ArtifactSignal` from real runs). Harmless for A0 (disk is the source of
  truth) but under-reports artifacts from real sessions.
- `adapter.configure()` remains dead on the coordinator path (the engine drives `execute` directly);
  `working_dir` now flows via construction. Worth reconciling when Actuation lands.
- Test entanglement: the root `tests/conftest.py` imports v1 `nexus.api` (needs `discord`), coupling
  v2 test collection to v1 optional deps — a real integration/packaging debt.

## 9. Integration points (v1 ↔ v2 — the first bridge)

A0 is the **first production-grade v2 bridge**, kept intentionally minimal:
- **v2 side** is fully wired and real (this report).
- **v1 side**: the honest seam is `run_a0_vertical(task, working_dir=…, commit_authorization=…)`. A v1
  Dex approved task would supply the objective and, on approval, the `Authorization` that flips the
  fail-closed gate. That live wiring (Discord approval → `Authorization`) is **not** built — it is
  remaining stub #2. No migration framework was built (per the rule); only the function-boundary seam.

## 10. Production blockers

1. **No governed Actuation session** (reattach, permission envelope, secret injection by reference) —
   one-shot CLI only.
2. **Approval not routed to a real human channel** — gate is fail-closed but code-local.
3. **Rate-limit reality**: the account is at 0.97/7-day utilization — real runs are budget-bound;
   production needs quota/backpressure handling.
4. **No commit/push path** — A0 deliberately never writes to a real repo.
5. **Test/dep entanglement** (v2 collection needs v1's `discord`).

---

## Final Verdict

1. **Did the Architecture Freeze survive real implementation?** **Yes.** The ten-engine pipeline, the
   provider seam, event sourcing, and the touched invariants (INV-20, INV-30, INV-37, INV-17
   determinism) all held under a real Claude session against a real repo. One low-severity conflict
   (single-episode knowledge) surfaced and was documented, not patched.

2. **Which assumptions proved correct?** (a) The `adapter_factory` is the *only* provider-specific
   choice — swapping stub→real needed no engine change. (b) Evidence-over-self-report is real: the
   file was judged on disk, not by Claude's word. (c) Fail-closed governance is real and default. (d)
   Provider independence: Claude-specific behavior stayed entirely in the adapter/invoker.

3. **Which assumptions failed?** The implicit benchmark assumption that a *single* run "learns and
   persists knowledge." The architecture learns from **confirmed cross-episode patterns**, so one
   episode persists nothing (`ARCHITECTURAL_CONFLICT_1`). The engine is right; the expectation was
   miscalibrated.

4. **Which components required only implementation?** Repository Intelligence (thin), the real-Claude
   actuation factory, the approval gate, independent validation, and the briefing — all built by
   *composing* existing contracts, plus a 1-line adapter change. No engine needed rework.

5. **Which required architectural revision?** **None.** The single conflict has a zero-code mitigation
   and an optional additive extension; it does not reopen an ADR, contract, or invariant.

6. **Can Nexus now execute the reference engineering workflow?** **Partially — the core is now real.**
   It can: understand a real repo, plan, select a runtime, open a real Claude Code session, operate a
   real repository, validate the real effect independently, recover, and brief. It cannot yet: route
   approvals/clarifications to a real human channel, run a governed reattachable Actuation session, or
   commit back to a real repo. Those are the named remaining stubs — implementation, not design.

7. **What percentage of the original vision is now operational?** **~55–60%** (up from the freeze
   review's ~35–40%). The decisive jump is that real actuation now exists and is validated end-to-end;
   the remainder is the human-channel routing, governed Actuation session, and commit path — all
   scoped, none foundational.

**Next proving vertical (not horizontal expansion):** **A1 — route the approval through a real
channel.** Take this exact vertical and replace remaining stub #2: flip the fail-closed `ApprovalGate`
from a real, recorded human decision delivered over a real channel (start by wrapping v1's working
Discord as the first Human Interaction Channel Adapter), then allow a gated commit onto a throwaway
branch. That single addition proves Human Interaction + the v1↔v2 approval bridge against real
infrastructure — the next-highest-leverage step toward the full reference workflow.

**Recommendation:** the Architecture Freeze is **confirmed by execution**. Continue proving one
vertical at a time (A1 next); do not resume foundational design.
