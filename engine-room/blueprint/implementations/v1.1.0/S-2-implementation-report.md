# S-2 — Default-Secure Sandbox Resolution: Implementation Report

> **Release line:** v1.1.0 "Containment" · **AP:** S-2 · **Track:** S (Sandbox) · **Status:** ✅ Complete
> **Closes:** A-006 R-01 (default host execution), R-02 (fail-open provider resolution).
> **Method:** strict TDD (red → green → regression). Branch `v1.1.0-planning`.
> **Authorization:** AP Authorization: S-2. Stops after S-2 (no S-3, no Nexus work).

---

## 1. Scope delivered

| Scope item | Delivered |
|---|---|
| 1. Eliminate unknown-provider fail-open | Unknown provider name now **raises `SandboxResolutionError`** (was `else → LocalSandboxProvider`) |
| 2. Fail-closed provider resolution | Disabled isolation + unknown provider both fail closed; no silent host fallback |
| 3. Default-secure selection | Real config with `sandbox.enabled=False` (the shipped default) **fails closed**; host requires explicit `enabled=true, provider=local` |
| 4. Preserve `SandboxManager` abstraction | Signature/usage unchanged; only `_resolve_provider` internals changed |
| 5. Preserve runtime adapter contracts | Adapters still call `SandboxManager(session, settings).execute(...)`; non-`NexusSettings` construction path retained |
| 6. Preserve audit logging | No audit code touched; `sandbox.*` lifecycle audit on resolved paths unchanged |

## 2. The resolution contract (after S-2)

| Input | Result |
|---|---|
| `settings` not `NexusSettings` (None / test double) or no `sandbox` | `LocalSandboxProvider` (non-production construction path, **retained**) |
| real `NexusSettings`, `sandbox.enabled=False` (**default**) | **`SandboxResolutionError`** (fail-closed) |
| `enabled=True`, provider `docker` | `DockerSandboxProvider` |
| `enabled=True`, provider `mock` | `MockSandboxProvider` |
| `enabled=True`, provider `local` | `LocalSandboxProvider` (deliberate, recognized host opt-in) |
| `enabled=True`, provider **unknown** | **`SandboxResolutionError`** (fail-closed) |

Provider names are matched case-insensitively against the recognized set `{docker, mock, local}`;
case never causes a fail-open.

## 3. Changes (minimal diff — 2 source files, 2 test files)

| File | Change |
|---|---|
| `nexus/core/exceptions.py` | **+** `SandboxResolutionError(ExecutionEngineError)` |
| `nexus/execution/sandbox/manager.py` | `_resolve_provider` rewritten fail-closed: disabled ⇒ raise; recognized-provider map; unknown ⇒ raise; non-`NexusSettings` ⇒ Local (retained). **+** import of `SandboxResolutionError` |
| `tests/unit/execution/test_sandbox_resolution.py` | **NEW** — 9 resolution tests (proof) |
| `tests/unit/execution/test_timeout_resolution.py` | Regression reconciliation: the Nexus `execute_command` timeout test now explicitly enables sandbox (`SandboxConfig(enabled=True, provider="mock")`) so it reaches the monkeypatched `execute` under the new fail-closed default. **No Nexus source change.** |

## 4. Design rationale (why this is minimal and correct)

- **Resolution runs in `SandboxManager.__init__`** (unchanged location). Fail-closed therefore raises at
  construction, *before* any sandbox is created — execution is impossible for unsafe/unknown config.
- **The non-`NexusSettings` path is deliberately retained as Local.** Production always supplies real
  `NexusSettings` (orchestrator passes `bot.settings`, `orchestrator.py:174`); the `None`/test-double
  path is a non-production construction convenience that runner unit tests and the e2e MVP
  (`MockDiscordService.bot = MagicMock()`) depend on. Changing it would have broken unrelated tests for
  no production gain — out of S-2's minimal-diff scope, and a candidate for the S-3 startup gate.
- **Host execution remains possible but only deliberately** (`enabled=true, provider=local`) — the
  explicit, recognized host acknowledgment. Loud startup auditing of this choice is **S-3** (deferred).

## 5. Constraint compliance

- TDD first ✅ · minimal diff ✅ · no opportunistic refactoring ✅ · **no Nexus changes** (source) ✅ ·
  no scheduler changes ✅ · no governance redesign ✅ · no runtime feature additions ✅ ·
  **no schema changes / no migrations** ✅ (only an exception class + resolver logic) ·
  no documentation rewrites ✅ (config defaults unchanged: `enabled` still defaults `False`).

## 6. Verification gates

| Gate | Result |
|---|---|
| New resolution tests | **9 passed** |
| Full suite | **152 passed** (143 prior + 9 new), 0 unresolved regressions |
| ruff `nexus/ tests/` | All checks passed |
| mypy `nexus/ --ignore-missing-imports` | Success: no issues in 57 source files |

(Run with the project venv `.venv/Scripts/python.exe`.)

## 7. Explicit proofs (required)

- **Unknown providers cannot execute:** `test_unknown_provider_fails_closed`,
  `test_unknown_provider_cannot_execute` — construction raises before `execute()` is reachable.
- **Missing isolation fails closed:** `test_disabled_sandbox_fails_closed`,
  `test_default_production_settings_fail_closed`.
- **Approved Docker path operates:** `test_docker_provider_resolves` (+ existing
  `test_docker_sandbox_command_construction` still green).

Details in `sandbox-resolution-validation.md`, `sandbox-failclosed-audit.md`,
`regression-validation-report.md`.

## 8. Boundary / stop

Stopped after S-2. **Not started:** S-3 (enforced policy, Docker availability probe, startup-validation
gate), any Nexus work, R-04 command-policy. **No commit made** (awaiting explicit instruction).

## 9. Status toward classification

S-2 closes R-01 + R-02 (the resolution half of "Safe by Default"). Full **Pilot Safe** still requires
S-3 (R-03/R-06/R-07) and S-4/R-05 — not in scope here. `architecture-status-summary.md` is **not**
updated yet (the sandbox row upgrades only when the full Pilot-Safe evidence set lands).
