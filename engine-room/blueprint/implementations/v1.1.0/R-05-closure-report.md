# R-05 Closure Report (S-4)

> Confirms closure of the cross-track shared risk **R-05 / AP-105 Gap 7** — Nexus file-tool host
> bypass — per the single resolution agreed in `R-05-shared-resolution.md`.

---

## 1. The risk (recap)

| | |
|---|---|
| **R-05 (A-006)** / **Gap 7 (AP-105)** | Nexus `read_file`/`write_file` touched the **host filesystem directly** (`nexus.py:88-105`), bypassing the sandbox — arbitrary host file read/write regardless of provider. |
| Severity | High (shared between the Sandbox and Nexus audits). |

## 2. Ownership honored (no duplicate solution)

Per `R-05-shared-resolution.md`:

| Concern | Owner | Realized in S-4 |
|---|---|---|
| Containment/path-confinement **mechanism** | **Track S** | `nexus/execution/sandbox/confinement.py::resolve_in_workspace` |
| File tools **adopt** the mechanism | **Track H** (file tools only) | `nexus.py` `read_file`/`write_file` call the seam |

The mechanism is implemented **once** in the sandbox package and consumed by Nexus — no Nexus-local
confinement, no duplication (Architecture Rule 9).

## 3. Resolution strategy delivered

The **always-on floor** from the R-05 design: workspace path-confinement.

- Every file path is resolved against the execution's approved workspace
  (`ExecutionRecord.repository`, the same cwd used for command execution).
- Paths that traverse out (`..`), are absolute outside the workspace, or symlink out are **refused
  fail-closed** (`WorkspaceConfinementError`) — no host FS access occurs.
- This holds under **any** provider (path-layer enforcement), satisfying the "guarantees hold under
  Docker and Local" requirement.

The **in-container ceiling** (file I/O executed inside the Docker container) is deferred as
defense-in-depth (see §6) — it is not required to eliminate the escape risk, which the floor closes.

## 4. Implementation order honored

`R-05-shared-resolution.md` §5 required the Track-S seam to precede Nexus adoption. In S-4 both land
together in the correct dependency order within one AP: the seam (`confinement.py`) is defined, then
the Nexus file tools consume it. No Track-H Nexus work (search/planning/cancellation/resume) was
started.

## 5. Proof of closure

| Claim | Proof |
|---|---|
| Nexus cannot read outside the workspace | `test_nexus_read_escape_denied` (secret content not returned) |
| Nexus cannot write outside the workspace | `test_nexus_write_escape_denied` (external file not created) |
| Traversal cannot escape | `test_parent_traversal_denied`, `test_deep_traversal_denied` |
| Approved access still works | `test_nexus_read_within_workspace_succeeds`, `test_nexus_write_within_workspace_succeeds` |
| Provider-independent | `test_confinement_independent_of_provider` |

All green within the full suite (**178 passed**, ruff + mypy clean).

## 6. Deferred (documented, not silently dropped)

- **In-container file I/O** under Docker (running file ops inside the container) — defense-in-depth
  ceiling; the host-side workspace-confined floor already prevents escape, and under Docker the
  workspace is the mounted volume.
- **Track-H Nexus work** (real search, planning, cancellation, resume) — out of S-4 scope.
- **R-04** command-blacklist hardening — governance-owned, separate.

## 7. Status

**R-05 is CLOSED** at the floor level (escape prevented, fail-closed, provider-independent), with the
in-container ceiling deferred as an enhancement. This was the last open risk for the Sandbox track;
combined with S-2/S-3, the sandbox now meets the **Pilot Safe** bar (`ADR-sandbox-safety-review`).
