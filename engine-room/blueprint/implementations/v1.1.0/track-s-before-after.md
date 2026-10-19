# Track S — Security Posture Before vs After

> Side-by-side of the execution sandbox before A-006 hardening and after Track S (S-2/S-3/S-4).
> Behavioral claims re-verified against current source (HEAD `2fd3ffc`); live gates 178 passed,
> ruff clean, mypy clean. Review-only — no code/test/implementation changes.

---

## 1. Resolution & default behavior

| Aspect | Before (A-006) | After (Track S) |
|---|---|---|
| `sandbox.enabled=False` (shipped default) | → `LocalSandboxProvider` → **host shell** (silent) | **`SandboxResolutionError`** at `SandboxManager.__init__` — refuses to run implicitly (R-01) |
| Unknown / misspelled provider | `else → LocalSandboxProvider` (**fail-open to host**) | **`SandboxResolutionError`**, no host fallback; matched vs `RECOGNIZED_PROVIDERS` (R-02) |
| Host execution | Implicit, any misconfig | Only via **deliberate** `enabled=true, provider=local`, **warned at startup** |
| Where resolution fails | n/a (never failed) | At **construction**, before any sandbox/process exists |
| Non-production construction (`settings=None`/double) | Local | Local (**retained** by design for adapter/e2e contracts) |

## 2. Policy enforcement honesty

| Aspect | Before | After |
|---|---|---|
| `SandboxPolicy` under Local | Built + audited, then **ignored** (decorative) | Still not enforced by Local **but declared**: `sandbox.created.policy_enforced=false` (R-03) |
| Provider self-description | None | `enforces_policy` flag (Docker `True`; Local/Mock/ABC `False`) |
| Operator visibility of unenforced policy | None | `sandbox_host_unsafe_at_startup` warning + per-execution `policy_enforced=false` in immutable ledger |

## 3. Startup & availability validation

| Aspect | Before | After |
|---|---|---|
| Sandbox config validated at boot | **No** (only A-001 owner gate) | **Yes** — `validate_sandbox_startup(settings)` in lifespan after owner gate (R-07) |
| Unknown provider at boot | Boots silently, fails at first command | **Boot aborts** (`ConfigurationError`, logged critical) |
| Docker availability | Discovered at first command spawn | **Probed at startup** (`ensure_available` → `docker version`); unavailable ⇒ **boot aborts** (R-06) |
| Failure discipline | Delayed runtime discovery | Fail-fast at boot (mirrors A-001); spawn fail-closed remains as defense-in-depth |

## 4. Agent file tools (Nexus)

| Aspect | Before | After |
|---|---|---|
| `read_file` / `write_file` | Raw `open()` on **any host path**; no manager, no confinement (R-05) | Resolve through `resolve_in_workspace(workspace, path)` before any FS access |
| Path traversal (`../`) | Unmitigated | `resolve()` collapses + `is_relative_to` rejects ⇒ `WorkspaceConfinementError` |
| Absolute-path escape | Unmitigated | Rejected unless inside workspace |
| Symlink escape | Unmitigated | `resolve()` follows links ⇒ escape rejected |
| Read vs write | Both unbounded | **Symmetric** — same seam, neither weaker |
| Provider dependence | n/a | **Provider-independent** (path-layer; holds under local/docker/mock) |
| Containment unit | Commands cwd-scoped; files unbounded | **One workspace** (`ExecutionRecord.repository`) for commands **and** files |

## 5. Audit (already a strength; preserved + extended)

| Aspect | Before | After |
|---|---|---|
| Command lifecycle audit | Complete, immutable (`sandbox.created/started/terminated/timeout/failure`) | Unchanged + **`policy_enforced`** honesty metadata on `sandbox.created` |
| Startup signals | None | `sandbox_startup_validated` / `sandbox_disabled_at_startup` / `sandbox_host_unsafe_at_startup` / `sandbox_startup_validation_failed` |
| File-tool outcomes | Not distinctly recorded | Recorded via existing `AgentStepRecord` trajectory (incl. denials naming the workspace + "fail-closed") |

## 6. Net classification movement

| | Before | After |
|---|---|---|
| Classification | **Unsafe By Default** (Experimental) | **Pilot Safe** (proposed; `ADR-sandbox-pilot-safe.md`) |
| Critical risks open | R-01, R-02 | **0** |
| Pilot-gating risks open | R-01, R-02, R-03, R-05, R-06, R-07 | **0** |
| Residual (out of charter) | — | R-04 (governance), R-08 (design-inherent), R-09 (partial) |
| Default posture | Runs on host silently | **Fails closed**; isolation is explicit, validated, honest |

## 7. Test-evidence delta

| Stage | Suite total | New tests | Focus |
|---|---|---|---|
| v1.0.1 baseline | 143 | — | pre-hardening |
| S-2 | 152 | +9 | resolution fail-closed |
| S-3 | 166 | +14 | startup gate, availability, policy honesty |
| S-4 | 178 | +12 | workspace confinement |

**Zero regressions** across the entire track; CLI runtimes (Gemini/Claude) and all non-sandbox
subsystems unaffected.

## 8. One-line summary

Track S converted the sandbox from **"silently runs on the host unless perfectly configured"** to
**"refuses to run unless safely and explicitly configured, tells the truth about what it enforces,
validates itself at boot, and confines agent file access to one workspace boundary"** — closing both
Critical risks and every Pilot-gating risk, with the remaining items bounded and tracked.
