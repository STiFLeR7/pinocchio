# File-Tool Security Review (S-4)

> Focused security review of the Nexus file tools after workspace confinement. Establishes the threat
> model addressed, residual considerations, and the audit story.

---

## 1. Threat model addressed

| Threat | Before (A-006 R-05 / AP-105 Gap 7) | After (S-4) |
|---|---|---|
| Arbitrary host file **read** (e.g. `/etc/passwd`, secrets, `.env`) | `read_file` opened any host path (`nexus.py:91`) | Confined to workspace; escape ⇒ fail-closed |
| Arbitrary host file **write** (e.g. overwrite system/config files, plant scripts) | `write_file` wrote any host path + `makedirs` (`nexus.py:100-102`) | Confined to workspace; escape ⇒ fail-closed |
| Path **traversal** (`../../`) | unmitigated | resolved + rejected |
| **Absolute-path** escape | unmitigated | rejected unless inside workspace |
| **Symlink** escape | unmitigated | `resolve()` follows links → escape rejected |

## 2. Enforcement properties

- **Fail-closed:** a non-conforming path raises `WorkspaceConfinementError`; the file operation does
  **not** execute (no `open`, no `makedirs`). The tool returns an error result.
- **Provider-independent:** enforced at the path layer, before any sandbox provider involvement — holds
  under `local`, `docker`, and `mock`.
- **Symmetric:** `read_file` and `write_file` use the identical seam; neither is weaker.
- **Workspace = the approved repository** (`ExecutionRecord.repository`), the same scope the
  `SandboxManager` uses as `cwd` for command execution — one containment unit for all execution paths.

## 3. Audit & observability

- File-tool outcomes — success and **denials** — are persisted in the immutable trajectory as
  `AgentStepRecord` rows (`thought`, `tool_name`, `tool_arguments`, `tool_result`). A confinement
  denial is a step whose `tool_result` states the path "resolves outside the approved workspace … 
  fail-closed", naming the workspace.
- Command execution retains its `sandbox.*` audit (incl. S-3 `policy_enforced`).
- No new audit event type was introduced (minimal diff); the existing agent-step ledger is the audit
  surface for file tools.

## 4. Interaction with other controls

- **Governance/approval:** unchanged and upstream — a goal is still governance-validated before the
  loop runs tools (Rule 5).
- **Sandbox provider (S-2/S-3):** complementary — commands get provider containment + fail-closed
  resolution; files get workspace confinement. The workspace is the shared anchor.
- **Default-secure (S-3):** if `execute_command` is used it is subject to the default-secure provider
  resolution; file tools are subject to confinement regardless.

## 5. Residual considerations (deferred / out of scope)

| Item | Status | Rationale |
|---|---|---|
| In-container file I/O under Docker | Deferred | Floor already prevents escape; ceiling is defense-in-depth |
| TOCTOU on resolved paths | Low risk / deferred | `resolve()` then immediate `open`; workspace is operator-approved; no privilege boundary crossed within workspace |
| Workspace itself containing sensitive files | Out of scope | The workspace is the operator-approved repository; confinement bounds access to it by design |
| R-04 command blacklist robustness | Out of scope | Governance-owned; separate item |
| Nexus honesty/lifecycle (search/plan/exit/terminate/resume) | Out of scope | Track-H work (AP-105 gaps) |

## 6. Verdict

The Nexus file tools are now **confined, symmetric, fail-closed, and provider-independent**, closing
the R-05 host-bypass. Residual items are defense-in-depth enhancements or explicitly out-of-scope
concerns, each recorded. File-tool security is sufficient for the **Pilot Safe** bar.
