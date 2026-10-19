# Sandbox Resolution Validation (S-2)

> Validation evidence that provider resolution is now default-secure and fail-closed. Maps each S-2
> requirement to the test that proves it. All tests run under the project venv.

---

## 1. Test inventory — `tests/unit/execution/test_sandbox_resolution.py` (9)

| Test | Asserts |
|---|---|
| `test_unknown_provider_fails_closed` | `enabled=True, provider="bogus-provider"` ⇒ `SandboxResolutionError` (no host fallback) |
| `test_unknown_provider_cannot_execute` | typo provider (`"dcoker"`) ⇒ raises at construction; `execute()` unreachable |
| `test_disabled_sandbox_fails_closed` | real `NexusSettings`, `enabled=False` ⇒ `SandboxResolutionError` |
| `test_default_production_settings_fail_closed` | `NexusSettings()` default (`enabled=False`) ⇒ raises; guards default unchanged |
| `test_docker_provider_resolves` | `enabled=True, provider="docker"` ⇒ `DockerSandboxProvider` |
| `test_mock_provider_resolves` | `enabled=True, provider="mock"` ⇒ `MockSandboxProvider` |
| `test_explicit_local_provider_resolves` | `enabled=True, provider="local"` ⇒ `LocalSandboxProvider` (deliberate host) |
| `test_provider_name_normalized` | `provider="DOCKER"` ⇒ `DockerSandboxProvider` (case-insensitive, no fail-open) |
| `test_non_nexussettings_preserves_local` | `settings=None` ⇒ `LocalSandboxProvider` (retained non-prod path) |

Result: **9 passed.**

## 2. Requirement → evidence matrix

| S-2 requirement | Evidence |
|---|---|
| Eliminate unknown-provider fail-open | `test_unknown_provider_fails_closed`, `test_unknown_provider_cannot_execute` |
| Fail-closed provider resolution | the two unknown-provider tests + `test_disabled_sandbox_fails_closed` |
| Default-secure selection | `test_default_production_settings_fail_closed` (shipped default ⇒ raise) |
| Preserve `SandboxManager` abstraction | all tests construct `SandboxManager(session, settings)` unchanged |
| Preserve runtime adapter contracts | `test_non_nexussettings_preserves_local` + full runner suites green (regression report) |
| Preserve audit logging | existing `test_sandbox.py` mock/docker/lifecycle audit tests still pass (regression report) |

## 3. TDD trace

- **Red:** `ImportError: cannot import name 'SandboxResolutionError'` (and behavior absent) before
  implementation — confirmed by running the new file first.
- **Green:** 9/9 after adding `SandboxResolutionError` and rewriting `_resolve_provider`.

## 4. Behavioral truth table (validated)

| `settings` | `enabled` | `provider` | Outcome |
|---|---|---|---|
| not `NexusSettings` | — | — | Local (retained) |
| `NexusSettings` | False | any | **raise** |
| `NexusSettings` | True | `docker`/`Docker` | Docker |
| `NexusSettings` | True | `mock` | Mock |
| `NexusSettings` | True | `local` | Local (deliberate) |
| `NexusSettings` | True | unknown | **raise** |

## 5. Verdict

**PASS.** Resolution is fail-closed for disabled isolation and unknown providers; recognized providers
resolve; host execution is reachable only as a deliberate, recognized choice; the non-production
construction path is preserved. R-01 (resolution half) and R-02 are validated.
