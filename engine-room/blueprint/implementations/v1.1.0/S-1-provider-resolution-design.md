# S-1 — Provider Resolution Design (v1.1.0)

> **Track S · Design only.** Replaces the fail-open provider resolution with a fail-closed, validated,
> availability-aware model. No code. Answers Q2 (what must fail closed) and Q4 (resolution).

---

## 1. Problem (evidence)

`SandboxManager._resolve_provider()` (`manager.py:34-53`) returns `LocalSandboxProvider` (host) for:
disabled (default), non-`NexusSettings`, missing config, `"local"`, **and any unknown provider name**
(`else: return LocalSandboxProvider()`, `manager.py:52-53`). Any typo or misconfig **fails open to the
host** (R-02, Critical). Docker availability is never checked before use (R-06).

## 2. To-be resolution contract (conceptual)

```
resolve_provider(config) :
  if config invalid / missing            -> FAIL CLOSED (refuse; startup gate catches earlier)
  provider = config.provider (normalized)
  match provider:
    "docker"        -> require Docker available; else FAIL CLOSED
    "mock"          -> test contexts only (rejected in production config)
    "host-unsafe"   -> allowed ONLY if explicitly acknowledged; emit loud audit + warning
    <unknown>       -> FAIL CLOSED (raise; NEVER fall back to host)
```

**Key inversions vs today:**
- The `else → Local` fallback is **removed**; unknown ⇒ raise (closes R-02).
- `enabled=False` no longer silently means "host"; the default posture is **isolation-required**
  (boundary-model §5). Host execution requires the explicit `host-unsafe` selection.
- `mock` is confined to test configuration and **rejected** when a production environment is detected
  (prevents the Nexus-style "test artifact in prod" failure mode, cross-ref AP-105 Cap 4).

## 3. Availability checking (Q4, R-06)

- **Docker probe:** before Docker is accepted as the active provider, verify the Docker runtime is
  reachable (a lightweight availability check). Probe result is **cached at startup** and re-checked
  defensively at execute-time.
- **On probe failure when Docker is required:** FAIL CLOSED with a clear, audited error — **no** silent
  downgrade to host. (This *extends* the existing manager-level fail-closed behavior on Docker spawn
  errors, `manager.py:172-179`, to also cover *availability*, not just spawn.)

## 4. Two-phase validation (Q2/Q3)

| Phase | Where | Action |
|---|---|---|
| **Startup** | `api.py` lifespan (mirrors A-001 `_validate_startup_configuration`) | Resolve + validate the configured provider once; abort boot on unknown/incoherent config; probe Docker if required; loudly audit `host-unsafe` | 
| **Execute-time** | `SandboxManager.execute` | Re-confirm the resolved provider + availability; fail closed on drift |

Startup validation is the sandbox analogue of the accepted A-001 owner-gate pattern — **fail-fast on
unsafe configuration** rather than discovering it at first command.

## 5. Normalization & aliases

Provider names are normalized (case/trim) before matching, but **normalization never invents a
fallback** — an unrecognized normalized value still fails closed. (Contrast the runtime registry's
alias handling in `runners/__init__.py:26-33`, which is a *known-alias* map, not an open fallback.)

## 6. Architecture preservation

- Lives entirely inside the existing `SandboxManager`/`SandboxProvider` contract — no new abstraction,
  no new execution path (Rules 1, 2, 9).
- Startup gate reuses the established lifespan-validation pattern (Rule 5/consistency).
- All resolution outcomes (selected provider, refusals, host-unsafe usage) are **audited** via the
  existing `SandboxAuditIntegration` (Rule 4).
- No governance/scheduler/memory/event change (Rules 3, 5, 6, 7).

## 7. Closes

R-02 (fail-open unknown provider), R-06 (no Docker validation), and the resolution half of R-01
(default no longer silently host). Tier: **Pilot Safe**.
