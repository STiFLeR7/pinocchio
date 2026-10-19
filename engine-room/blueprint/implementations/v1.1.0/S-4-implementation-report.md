# S-4 — Workspace Confinement & R-05 Closure: Implementation Report

> **Release line:** v1.1.0 "Containment" · **AP:** S-4 · **Track:** S (Sandbox) ∩ H (Nexus file tools)
> **Status:** ✅ Complete · **Closes:** A-006 **R-05** / AP-105 **Gap 7** (Nexus file-tool host bypass).
> **Method:** strict TDD (red → green → regression). Branch `v1.1.0-planning`.
> **Authorization:** AP Authorization: S-4. Stops after S-4 (no Nexus Track-H work).

---

## 1. Objective delivered

A **single containment boundary** for all runtime execution paths: command execution remains
cwd-scoped via `SandboxManager`, and Nexus file operations are now confined to the same approved
**workspace** via a shared path-confinement seam. Agent file tools can no longer read or write host
paths outside the workspace.

## 2. Scope → delivered

| Scope item | Delivered |
|---|---|
| 1. Eliminate Nexus file-tool bypass | `read_file`/`write_file` route through `resolve_in_workspace` before any host FS access |
| 2. Implement workspace confinement | `nexus/execution/sandbox/confinement.py::resolve_in_workspace` — fail-closed on traversal/escape |
| 3. File ops obey the same containment model as commands | Both scoped to the execution's workspace (`ExecutionRecord.repository`); commands via `SandboxManager(cwd)`, files via `resolve_in_workspace(workspace)` |
| 4. Preserve runtime abstraction | Nexus stays an `AgentRuntimeAdapter`; only file-tool internals changed; no new tools |
| 5. Preserve governance boundaries | Governance/approval gate untouched; confinement is downstream of `validate_goal` |
| 6. Preserve scheduler architecture | No scheduler changes |
| 7. Preserve event architecture | No new/changed events; file-tool outcomes recorded via existing `agent_steps` |

## 3. Required validation questions — answers

1. **Can Nexus access files outside the workspace?** **No.** `resolve_in_workspace` raises
   `WorkspaceConfinementError` (caught → error result, no FS access). Proof:
   `test_nexus_read_escape_denied`, `test_nexus_write_escape_denied`.
2. **Can path traversal escape confinement?** **No.** Paths are resolved (`..` collapsed, symlinks
   followed) and must be `is_relative_to` the workspace. Proof: `test_parent_traversal_denied`,
   `test_deep_traversal_denied`.
3. **Are read and write equally constrained?** **Yes.** Both call the same seam. Proof:
   `test_read_and_write_equally_constrained`.
4. **Do guarantees hold under Docker and Local providers?** **Yes.** Confinement is enforced at the
   **path layer**, before/independent of the provider; under Docker the workspace is also the mounted
   `/workspace` volume, so host-side workspace-confined access is coherent with the container.
   Proof: `test_confinement_independent_of_provider` (docker-configured settings) + file tools never
   consult the provider for the path check.
5. **What is audited?** File-tool operations — including **denials** — are recorded in the immutable
   trajectory via `AgentStepRecord` (`thought`/`tool_name`/`tool_arguments`/`tool_result`); a denial
   appears as a step whose `tool_result` names the workspace and "fail-closed". Command execution
   continues to audit via `sandbox.*` events (incl. `policy_enforced` from S-3). No new audit plumbing
   was added (minimal diff).
6. **What remains deferred?** In-container file I/O (running file ops *inside* the Docker container
   rather than host-side-within-workspace) as a defense-in-depth ceiling — not required to close R-05's
   escape risk. Also deferred (out of scope): all Track-H Nexus work (search, planning, cancellation,
   resume) and R-04 command-policy hardening (governance-owned).

## 4. Changes (minimal diff)

| File | Change |
|---|---|
| `nexus/core/exceptions.py` | **+** `WorkspaceConfinementError(ExecutionEngineError)` |
| `nexus/execution/sandbox/confinement.py` | **NEW** — `resolve_in_workspace(workspace, requested_path)` (the Track-S-owned seam) |
| `nexus/execution/sandbox/__init__.py` | export `resolve_in_workspace` |
| `nexus/execution/runners/nexus.py` | **+** `_workspace_cwd()` helper; `read_file`/`write_file` resolve via `resolve_in_workspace` before FS access |
| `tests/unit/execution/test_workspace_confinement.py` | **NEW** — 12 tests (seam + Nexus integration) |

**No** schema changes, migrations, governance/scheduler/event changes, new Nexus tools, or
search/planning/cancellation/resume.

## 5. Design rationale

- **Single mechanism, single owner (R-05 resolved once).** The confinement seam lives in the sandbox
  package (Track S owns it); Nexus consumes it (Track H). No duplicate solution
  (`R-05-shared-resolution.md`).
- **Path-confinement floor.** `resolve()` + `is_relative_to(workspace)` collapses `..`, follows
  symlinks (so a symlink escaping the workspace is also refused), and rejects absolute paths outside
  the workspace — a robust, provider-independent floor.
- **Command path untouched.** `execute_command` already routes through `SandboxManager`; not modified
  (no opportunistic refactoring). The workspace is the unifying containment unit for both.
- **Fail-closed via existing error path.** A confinement violation surfaces as the tool's error result
  with no FS access — consistent with the existing file-tool error handling; the agent step records it.

## 6. Constraint compliance

TDD-first ✅ · minimal diff ✅ · **no Nexus feature expansion** (confinement of existing tools, no new
tools) ✅ · no search/planning/cancellation/resume ✅ · no schema/migrations ✅ · no doc rewrites ✅ ·
no opportunistic refactoring ✅ · runtime abstraction / governance / scheduler / event architecture
preserved ✅.

## 7. Verification gates

| Gate | Result |
|---|---|
| New S-4 tests | **12 passed** |
| Full suite | **178 passed** (166 prior + 12), 0 regressions |
| ruff `nexus/ tests/` | All checks passed |
| mypy `nexus/ --ignore-missing-imports` | Success: no issues in 58 source files |

## 8. Explicit proofs (required)

- **Path traversal fails:** `test_parent_traversal_denied`, `test_deep_traversal_denied`.
- **Workspace escape fails:** `test_absolute_escape_denied`, `test_nexus_read_escape_denied`,
  `test_nexus_write_escape_denied`.
- **Approved workspace access succeeds:** `test_valid_relative_path_allowed`,
  `test_nexus_read_within_workspace_succeeds`, `test_nexus_write_within_workspace_succeeds`.
- **Existing CLI runtimes unaffected:** `test_gemini.py` + `test_claude.py` (12) green; CLI runtimes
  have no file-tool path, so confinement does not apply to or alter them.

## 9. Boundary / stop

Stopped after S-4. **Not started:** any Nexus Track-H implementation (H-2…H-5). **No commit made.**

## 10. Status toward classification

S-4 closes **R-05**. With S-2 (R-01/R-02) + S-3 (R-03/R-06/R-07) + S-4 (R-05), the **Sandbox** track's
v1.1.0 risk set is complete → the sandbox now meets the **Pilot Safe** bar defined in
`ADR-sandbox-safety-review`. A status upgrade in `architecture-status-summary.md` (Sandbox:
Experimental → Pilot Safe) is now **evidence-supported** — recommended as a follow-up doc step (not
performed here, per "no documentation rewrites").
