# Sandbox Startup Validation (S-3)

> Validation evidence that the sandbox startup gate refuses unsafe/incoherent configuration at boot and
> verifies provider availability before any runtime execution (R-06, R-07). Mirrors the accepted A-001
> owner-gate pattern.

---

## 1. The gate

`validate_sandbox_startup(settings)` (`nexus/execution/sandbox/manager.py`) is called in the FastAPI
lifespan immediately after the A-001 owner gate (`nexus/api.py`). On `ConfigurationError` it logs
`sandbox_startup_validation_failed` (critical) and re-raises → the application **does not start**.

## 2. Decision table (validated)

| `sandbox` config | Gate outcome | Log |
|---|---|---|
| not `NexusSettings` / `enabled=False` | **allow boot** (safe; runtime fails closed per S-2) | `sandbox_disabled_at_startup` (warning) |
| `enabled=True`, provider unknown | **abort boot** (`ConfigurationError`) | `sandbox_startup_validation_failed` (critical) |
| `enabled=True`, `docker`, **unavailable** | **abort boot** (`ConfigurationError`) | critical |
| `enabled=True`, `docker`, available | allow boot | `sandbox_startup_validated` (info) |
| `enabled=True`, `local` (non-enforcing) | allow boot (deliberate host) | `sandbox_host_unsafe_at_startup` (warning) |
| `enabled=True`, `mock` | allow boot (test provider) | `sandbox_startup_validated` (info) |

## 3. Test inventory — `tests/unit/execution/test_sandbox_enforcement.py`

| Test | Asserts |
|---|---|
| `test_startup_disabled_sandbox_does_not_abort` | disabled ⇒ no raise (warned) |
| `test_startup_unknown_provider_aborts` | unknown provider ⇒ `ConfigurationError` |
| `test_startup_docker_unavailable_aborts` | docker probe fails ⇒ `ConfigurationError` |
| `test_startup_docker_available_passes` | docker available ⇒ no raise |
| `test_startup_local_host_unsafe_passes` | local ⇒ no raise (warned) |
| `test_startup_mock_passes` | mock ⇒ no raise |
| `test_docker_ensure_available_raises_when_missing` | `docker` binary absent ⇒ `SandboxUnavailableError` |
| `test_docker_ensure_available_raises_on_nonzero` | `docker version` exit≠0 ⇒ `SandboxUnavailableError` |
| `test_local_provider_always_available` | local probe ⇒ no-op |

Result: all pass (part of the 14 S-3 tests).

## 4. Requirement → evidence

| Requirement | Evidence |
|---|---|
| Validate config at startup (R-07) | gate wired in lifespan; unknown-provider + docker-unavailable abort tests |
| Verify provider availability before execution (R-06) | `ensure_available` Docker probe; startup runs it before any command executes |
| Eliminate delayed runtime discovery | unsafe Docker config aborts at **boot**, not at first command (abort tests) |
| Fail-fast, no degraded mode | `ConfigurationError` re-raised in lifespan (same as A-001) |

## 5. Defense in depth

Startup is the primary, fail-fast check. If it is bypassed (e.g. a provider becomes unavailable after
boot), the existing Docker spawn fail-closed (`manager.execute` spawn `except` → `sandbox.failure` +
raise) still refuses with **no host fallback** — preserving the S-2 guarantee.

## 6. Verdict

**PASS.** The startup gate refuses incoherent config and unavailable policy-enforcing providers at boot,
verifies availability before any execution, and fails fast with no degraded mode — eliminating delayed
runtime discovery of unsafe sandbox states.
