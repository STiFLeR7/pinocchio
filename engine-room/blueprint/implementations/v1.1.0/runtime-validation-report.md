# Runtime Validation Report

> **Milestone:** v1.1.0 "Containment" · Phases 4 + 6 · **Status:** ✅ validated (safe mode).

---

## 1. Registry resolution

After the branding migration, the runtime registry resolves all runtimes plus the back-compat alias
(captured from the live onboarding run, runtime stage):

```
runtime 'nexus'         resolves -> NexusRuntimeAdapter
runtime 'gemini'        resolves -> GeminiRuntimeAdapter
runtime 'claude'        resolves -> ClaudeRuntimeAdapter
legacy alias 'hermes'   resolves -> NexusRuntimeAdapter   (back-compat)
```

- `register("nexus")` is the primary id; `get_adapter_cls` maps `hermes` / `hermes_agent` → `nexus`,
  so persisted `runner="hermes"` execution records continue to resolve.
- Registration is **import-triggered**; the resolver imports all three adapter modules before
  resolving (the onboarding stage was corrected to do the same after an initial false-fail).

## 2. Runtime maturity (truthful)

| Runtime | Kind | Maturity | Notes |
|---|---|---|---|
| `nexus` (was `hermes`) | `AgentRuntimeAdapter` (in-house) | **Pilot** (H-4) | fail-fast init, configurable budget, terminate, cancellation, TIMED_OUT, resume; needs a real injected `SearchProvider` for production web tools |
| `gemini` | `CLIRuntimeAdapter` | **Stub** | subprocess shell runner; no real Gemini integration |
| `claude` | `CLIRuntimeAdapter` | **Stub** | subprocess shell runner; no real Claude integration |

> Phase 4 requested "execute Gemini and Claude using live infrastructure." This is **not possible**
> as written — both are stubs. Only the `nexus` agent is a real autonomous runtime. Live execution of
> all runtimes was **deferred** (safe-mode decision); no runs were performed.

## 3. Contract & safety invariants (preserved)

- `BaseRuntimeAdapter` / `CLIRuntimeAdapter` / `AgentRuntimeAdapter` hierarchy unchanged.
- `resume_goal` remains adapter-local to `NexusRuntimeAdapter` (not on the ABC) — CLI adapters
  untouched.
- `resolve_execution_timeout` (ADR-010 / A-002) honored; `runtime="nexus"` written on new records.
- Governance re-validated on `resume_goal`; S-4 workspace confinement intact (covered by
  `test_workspace_confinement.py`, still green post-rename).

## 4. Validation

| Gate | Result |
|---|---|
| pytest | **219 passed** |
| ruff | All checks passed |
| mypy (`nexus/ --ignore-missing-imports`) | Success, 61 source files |

Runtime-specific coverage: `test_nexus_agent.py`, `test_nexus_agent_honesty.py`,
`test_nexus_agent_lifecycle.py` (incl. the new alias test), `test_timeout_resolution.py`,
`test_workspace_confinement.py` — all green.
