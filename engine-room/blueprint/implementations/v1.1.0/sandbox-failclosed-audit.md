# Sandbox Fail-Closed Audit (S-2)

> Documents the fail-closed behavior and its auditability characteristics — specifically that a refused
> resolution produces **no** sandbox lifecycle and is observable to the caller, while existing audit
> behavior on resolved paths is unchanged.

---

## 1. Where fail-closed happens

Resolution runs in `SandboxManager.__init__` → `_resolve_provider()`. A fail-closed condition raises
`SandboxResolutionError` **at construction**, i.e. **before** `SandboxManager.execute()` runs and
therefore before any `sandbox.created` / `sandbox.started` audit event is emitted.

```
SandboxManager(session, settings)        # __init__ → _resolve_provider()
   ├─ unsafe/unknown config  ─► raise SandboxResolutionError   (no sandbox created, no execution)
   └─ safe config            ─► provider set → execute() proceeds → audit as before
```

## 2. Auditability of a refusal

| Property | Behavior |
|---|---|
| Sandbox lifecycle audit on refusal | **None emitted** — no `sandbox.created`/`started`/`terminated` |
| Meaning of that absence | **Provable non-execution** — if no `sandbox.created` row exists for an attempted run, nothing executed |
| Signal to caller | `SandboxResolutionError` (a `NexusError`/`ExecutionEngineError`) propagates to the runner/orchestrator, which surface/log it via their existing error handling |
| Existing audit on resolved paths | **Unchanged** — `sandbox.created`, `sandbox.started`, `sandbox.terminated`/`timeout`/`failure` still written exactly as before (`manager.py` execute path untouched) |

**Design choice (scope-bounded):** S-2 does **not** add a new "refusal" audit event. Resolution is
synchronous (`__init__`) and pre-execution; emitting a DB audit there would require restructuring to an
async path — out of S-2's minimal-diff scope. The fail-closed signal is the **raised exception** plus
the **absence of any sandbox lifecycle record**. A dedicated, loudly-audited refusal/`host-unsafe`
acknowledgment belongs to the **S-3 startup-validation gate** (deferred).

## 3. Consistency with existing fail-closed precedent

This mirrors the accepted **A-001** pattern: the owner-gate refuses unsafe startup by raising
`ConfigurationError` (logged, not DB-audited at the refusal point). S-2 refuses unsafe execution by
raising `SandboxResolutionError` before any sandbox exists — same "raise-before-effect, no partial
state" discipline.

## 4. Preserved audit behavior (evidence)

The existing sandbox audit tests remain green (see `regression-validation-report.md`):
`test_mock_sandbox_success_execution` (`sandbox.created/started/terminated`),
`test_mock_sandbox_failure_execution` (`sandbox.failure`),
`test_mock_sandbox_timeout_execution` (`sandbox.timeout`) — all unchanged. Requirement #6 (preserve
audit logging) is satisfied.

## 5. Verdict

Fail-closed is **safe and observable**: unsafe/unknown configurations cannot create a sandbox or
execute; the refusal surfaces as an exception with no partial sandbox state; resolved-path audit is
byte-for-byte unchanged. Richer refusal auditing is intentionally deferred to S-3.
