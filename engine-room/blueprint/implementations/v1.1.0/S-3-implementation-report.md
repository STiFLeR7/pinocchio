# S-3 — Sandbox Enforcement & Startup Validation: Implementation Report

> **Release line:** v1.1.0 "Containment" · **AP:** S-3 · **Track:** S (Sandbox) · **Status:** ✅ Complete
> **Closes:** A-006 R-03 (decorative policy), R-06 (no Docker availability validation),
> R-07 (no startup validation). **Preserves** all S-2 fail-closed guarantees (R-01, R-02).
> **Method:** strict TDD (red → green → regression). Branch `v1.1.0-planning`.
> **Authorization:** AP Authorization: S-3. Stops after S-3 (no S-4, no Nexus work).

---

## 1. Objectives delivered

| Objective | Delivered |
|---|---|
| 1. Enforce policy-or-refuse | Policy-enforcing provider (Docker) must be **available or startup refuses**; non-enforcing provider (local) is **declared, not pretended** (`policy_enforced` flag + loud warning) |
| 2. Validate sandbox config at startup | `validate_sandbox_startup()` wired into the lifespan (mirrors A-001 owner gate) |
| 3. Verify provider availability before runtime execution | `SandboxProvider.ensure_available()`; Docker probes `docker version`; checked at startup (before any execution) |
| 4. Eliminate delayed runtime discovery | Unknown provider / unavailable Docker **abort boot** instead of surfacing at first command |
| 5. Preserve S-2 fail-closed | `_resolve_provider` fail-closed branches unchanged; `SandboxUnavailableError` subclasses `SandboxResolutionError`; `test_s2_failclosed_preserved` proves it |

## 2. Required questions — answers (evidence in deliverables)

1. **Docker configured but unavailable?** Startup **aborts** — `validate_sandbox_startup` calls
   `DockerSandboxProvider.ensure_available()` → `SandboxUnavailableError` → wrapped to
   `ConfigurationError` → lifespan logs `sandbox_startup_validation_failed` (critical) and re-raises →
   **app does not start**. Defense in depth: if startup is bypassed, the existing Docker spawn
   fail-closed (`manager.py` spawn `except`) still refuses — no host fallback.
2. **Policy cannot be enforced?** The enforcing provider (Docker) must be available or we **refuse**
   (above). A non-enforcing provider (`local`) is allowed only as a deliberate choice and is **declared**
   — `sandbox.created` audit carries `policy_enforced=false` and startup emits a loud
   `sandbox_host_unsafe_at_startup` warning. Never pretended (closes R-03).
3. **Configuration internally inconsistent?** Unknown/unrecognized provider with `enabled=True` →
   `ConfigurationError` at startup (abort). (Disabled/unconfigured → warned, safe — execution still
   fails closed per S-2.)
4. **Startup validation fails?** `ConfigurationError` is logged `critical` and re-raised in the
   lifespan → **application refuses to start** (fail-fast, identical discipline to A-001).
5. **What events are audited?** See `sandbox-failure-matrix.md` §audit. DB (immutable `AuditLogRecord`):
   `sandbox.created` (**now incl. `policy_enforced`**), `sandbox.started`,
   `sandbox.terminated`/`timeout`/`failure`. Startup (structured logs): `sandbox_startup_validated`
   (info), `sandbox_disabled_at_startup` / `sandbox_host_unsafe_at_startup` (warning),
   `sandbox_startup_validation_failed` (critical). Every host-unsafe **execution** is recorded in the
   ledger via `policy_enforced=false`.

## 3. Changes (minimal diff — 5 source files, 1 new test file)

| File | Change |
|---|---|
| `nexus/core/exceptions.py` | **+** `SandboxUnavailableError(SandboxResolutionError)` (fail-closed availability) |
| `nexus/execution/sandbox/provider.py` | **+** `enforces_policy` flag (Docker True; ABC/Local/Mock False); **+** `ensure_available()` (ABC no-op; Docker probes `docker version`); **+** module `RECOGNIZED_PROVIDERS` registry |
| `nexus/execution/sandbox/manager.py` | `_resolve_provider` uses shared `RECOGNIZED_PROVIDERS` (S-2 fail-closed branches intact); `sandbox.created` audit gains `policy_enforced`; **+** `validate_sandbox_startup()` |
| `nexus/execution/sandbox/__init__.py` | export `validate_sandbox_startup`, `RECOGNIZED_PROVIDERS` |
| `nexus/api.py` | call `await validate_sandbox_startup(settings)` in lifespan after the A-001 gate; abort boot on `ConfigurationError` |
| `tests/unit/execution/test_sandbox_enforcement.py` | **NEW** — 14 tests (startup, availability, enforcement honesty, S-2 preservation) |

## 4. Design rationale (minimal & non-disruptive)

- **Single registry (`RECOGNIZED_PROVIDERS`)** is shared by resolution and startup validation — no
  duplicated provider knowledge, no hidden coupling (Architecture Rule 9).
- **Availability verified at startup, not per-execution.** Startup occurs before any runtime execution
  (satisfies "before runtime execution" + "eliminate delayed discovery"); runtime Docker failures
  remain covered by the existing spawn fail-closed. This avoided touching `execute()`'s happy path and
  the existing `test_docker_sandbox_command_construction` flow (minimal diff).
- **Honest audit, not behavior change.** The `policy_enforced` field is metadata on the existing
  `sandbox.created` event; execution behavior is unchanged. Ends the "decorative policy" pretense (R-03).
- **Startup uses logs + ConfigurationError** (consistent with A-001), reserving the immutable DB ledger
  for actual executions (incl. host-unsafe ones via `policy_enforced=false`).

## 5. Constraint compliance

TDD-first ✅ · minimal diff ✅ · no opportunistic refactoring (registry extraction is required to avoid
duplication) ✅ · **no Nexus changes** ✅ · no scheduler changes ✅ · no governance redesign ✅ · no
runtime feature additions ✅ · **no schema changes / no migrations** ✅ · no documentation rewrites ✅ ·
**SandboxManager abstraction preserved** (signature/usage unchanged) ✅.

## 6. Verification gates

| Gate | Result |
|---|---|
| New S-3 tests | **14 passed** |
| Full suite | **166 passed** (152 prior + 14), 0 unresolved regressions |
| ruff `nexus/ tests/` | All checks passed |
| mypy `nexus/ --ignore-missing-imports` | Success: no issues in 57 source files |

(Run with project venv `.venv/Scripts/python.exe`.)

## 7. Explicit proofs (required)

- **Docker-unavailable fails closed:** `test_startup_docker_unavailable_aborts`,
  `test_docker_ensure_available_raises_when_missing`, `test_docker_ensure_available_raises_on_nonzero`.
- **Policy-enforcement failures fail closed:** Docker (the enforcer) unavailable → abort (above);
  honesty: `test_execute_audit_declares_policy_enforcement`, `test_*_enforce_policy_flag`.
- **Startup validation prevents unsafe runtime states:** `test_startup_unknown_provider_aborts`,
  `test_startup_docker_unavailable_aborts` (boot aborts before any execution).
- **S-2 behavior unchanged:** `test_s2_failclosed_preserved` + all 9 S-2 tests still green.

## 8. Boundary / stop

Stopped after S-3. **Not started:** S-4 (R-05 file-tool confinement seam, optional R-04 command policy),
any Nexus work. **No commit made** (awaiting explicit instruction).

## 9. Status toward classification

S-3 closes R-03, R-06, R-07; with S-2 (R-01, R-02) the sandbox is now **default-secure + fail-closed +
enforcement-honest + boot-validated**. The remaining gap to **Pilot Safe** is **R-05** (Nexus file-tool
host bypass), owned by **S-4** (with Track H). `architecture-status-summary.md` is therefore **not yet**
upgraded.
