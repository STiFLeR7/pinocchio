# Sandbox Failure Matrix (S-3)

> Authoritative matrix of every sandbox failure/edge condition after S-2 + S-3: trigger → phase →
> outcome → signal/audit. Demonstrates uniform fail-closed behavior and answers "what events are
> audited."

---

## 1. Failure / edge matrix

| # | Condition | Phase | Outcome | Signal / exception | Audited as |
|---|---|---|---|---|---|
| 1 | `enabled=False` / unconfigured (real settings) | resolution (S-2) | **fail closed** (no execution) | `SandboxResolutionError` | none created (no `sandbox.*`); startup log `sandbox_disabled_at_startup` |
| 2 | Unknown provider name | resolution (S-2) | **fail closed** | `SandboxResolutionError` | none created; startup abort log if at boot |
| 3 | Unknown provider, `enabled=True` | startup (S-3) | **abort boot** | `ConfigurationError` | `sandbox_startup_validation_failed` (critical log) |
| 4 | Docker configured, **unavailable** (binary/daemon) | startup (S-3) | **abort boot** | `SandboxUnavailableError` → `ConfigurationError` | `sandbox_startup_validation_failed` (critical log) |
| 5 | Docker configured, available | startup (S-3) | boot OK | — | `sandbox_startup_validated` (info log) |
| 6 | Local (host) selected | startup (S-3) | boot OK (deliberate) | — | `sandbox_host_unsafe_at_startup` (warning log) |
| 7 | Docker becomes unavailable after boot | execution (spawn) | **fail closed** (no host fallback) | spawn error re-raised | `sandbox.failure` (DB) |
| 8 | Command exits non-zero | execution | recorded failure | (returns proc) | `sandbox.failure` (DB) |
| 9 | Command times out | execution | recorded timeout | (returns proc) | `sandbox.timeout` (DB) |
| 10 | Command succeeds | execution | success | — | `sandbox.created` (+`policy_enforced`), `sandbox.started`, `sandbox.terminated` (DB) |
| 11 | Host (local) execution runs | execution | runs on host (declared) | — | `sandbox.created` with **`policy_enforced=false`** (DB) |
| 12 | `settings` not `NexusSettings` (test/non-prod) | resolution | Local (retained, S-2) | — | normal `sandbox.*` (DB) |

**Invariant:** every unsafe/unknown/unavailable condition (#1–#4, #7) results in **refusal**, never host
fallback. Host execution (#6, #11) occurs only via a deliberate `enabled=True, provider=local` choice and
is **declared** in both logs and the immutable ledger.

## 2. What events are audited (answering required question 5)

### DB ledger (immutable `AuditLogRecord`, `component="sandbox_manager"`) — execution time
- `sandbox.created` — **now includes `policy_enforced`** (true under Docker, false under local/mock)
- `sandbox.started`
- `sandbox.terminated` (exit 0) / `sandbox.timeout` / `sandbox.failure`

These are unchanged in structure except the added `policy_enforced` honesty field; existing audit tests
(`test_sandbox.py`) remain green.

### Startup structured logs (no DB dependency at the gate) — boot time
- `sandbox_startup_validated` (info) — provider validated/available
- `sandbox_disabled_at_startup` (warning) — disabled; runtime will fail closed
- `sandbox_host_unsafe_at_startup` (warning) — non-enforcing provider chosen
- `sandbox_startup_validation_failed` (critical) — boot aborted (unknown provider / unavailable Docker)

This split mirrors A-001 (startup → logs + `ConfigurationError`; runtime effects → DB ledger). Host-unsafe
**executions** are still durably recorded in the ledger via `policy_enforced=false`.

## 3. Exception hierarchy (fail-closed preserved)

```
NexusError
└─ ExecutionEngineError
   └─ SandboxResolutionError        (S-2: disabled / unknown provider — fail closed)
      └─ SandboxUnavailableError    (S-3: enforcing provider unavailable — fail closed)
ConfigurationError                  (startup-fatal; raised by the gate, re-raised in lifespan)
```

`SandboxUnavailableError` subclassing `SandboxResolutionError` means any existing S-2 fail-closed
handling automatically covers availability failures — S-2 guarantees preserved.

## 4. Verdict

Uniform fail-closed across resolution, startup, and execution; host execution is the only non-isolated
path and is deliberate + declared + ledger-recorded. The matrix is fully covered by the S-2 (9) + S-3
(14) test sets.
