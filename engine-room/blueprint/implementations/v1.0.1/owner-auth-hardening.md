# A-001 — Owner Authentication Hardening (Fail-Closed)

> **Release:** Nexus v1.0.1 "Alignment" · **AP:** AP-102 · **Finding:** A-001 (Priority 0)
> **Type:** Root-cause safety fix (TDD) · **Status:** ✅ Implemented & validated

---

## 1. Defect (v1.0.0)

`ApprovalService.evaluate_approval` guarded authorization with `if self.owner_ids and …`
(`nexus/approvals/service.py:94`). When `owner_ids` was empty — the **config default**
(`nexus/config.py:42` `owner_ids: list[int] = Field(default_factory=list)`) — the guard
short-circuited to `False`, so the unauthorized-raise was never reached and **any** `decided_by`
could authorize governed execution. Nothing at startup rejected an empty owner configuration.

This nullified the system's core guarantee (human approval before execution). Validated in AP-101
(`alignment-validation.md` §A-001).

## 2. Target (accepted finding)

Fail closed. If no owner IDs are configured: **application startup fails** (clear operator error;
no degraded/warning/fallback mode), AND `ApprovalService` **independently denies** authorization as
defense-in-depth.

## 3. Implementation

Two layers, both minimal and root-cause:

### Layer 1 — Startup gate (`nexus/api.py`)
New `_validate_startup_configuration(settings)` raises `ConfigurationError` when
`settings.discord.owner_ids` is empty (`api.py` new function). It is called at the very top of the
FastAPI `lifespan` startup (immediately after logging init), and a raised error is logged at
`critical` and re-raised, preventing the app from reaching `yield`/serving:

```python
# A-001: fail-closed safety gate — refuse to start without configured owners.
try:
    _validate_startup_configuration(settings)
except ConfigurationError as exc:
    logger.critical("startup_validation_failed", error=str(exc))
    raise
```

Operator-facing message:
> *Startup aborted: no Discord owner IDs configured (discord.owner_ids is empty). Approval
> authorization would be disabled (fail-open), which is not permitted. Set DISCORD_OWNERS
> (comma-separated IDs) or discord.owner_ids and restart.*

### Layer 2 — Defense-in-depth in the service (`nexus/approvals/service.py`)
`evaluate_approval` now denies when `owner_ids` is empty, before any decision logic:

```python
if not self.owner_ids:
    raise ApprovalEngineError(
        "Approval authorization is disabled: no owner IDs are configured. "
        "Refusing to authorize (fail-closed)."
    )
if str(decided_by) not in self.owner_ids:
    raise ApprovalEngineError(f"User {decided_by} is not authorized to grant approvals.")
```

**Scope note:** the change is in `evaluate_approval` (the authorization chokepoint), **not** the
constructor — so `sweep_expired_approvals` (which may legitimately run without owner context and is
not an authorization action) is unaffected. Production callers (orchestrator ×3, Discord bot) all
pass `settings.discord.owner_ids` to `ApprovalService` (verified at `orchestrator.py:71-76,128-133,
233-238`, `bot.py:74-76`), so valid configurations behave exactly as before.

## 4. Why this is correct (root cause, not symptom)

The root cause was an authorization guard whose *default state was "allow"*. The fix inverts the
default to "deny" at the only authorization site, and adds a startup gate so the unsafe state can
never reach runtime. No authorization *model* change (still an owner-ID allowlist) — constraint
compliant.

## 5. Tests (TDD)

New `tests/unit/approvals/test_owner_auth_hardening.py` (4) and
`tests/unit/test_startup_validation.py` (2):

| Test | Asserts |
|---|---|
| `test_evaluate_approval_denied_when_owner_ids_empty` | empty list → raises; task stays BLOCKED; gate stays closed |
| `test_evaluate_approval_denied_when_owner_ids_none` | `None`→`[]` → raises |
| `test_valid_owner_behaves_unchanged` | configured owner approves → task ACTIVE, gate open |
| `test_non_owner_still_rejected_with_configured_owners` | non-owner still rejected (regression) |
| `test_startup_fails_with_empty_owner_ids` | `_validate_startup_configuration([])` raises `ConfigurationError` |
| `test_startup_succeeds_with_owner_ids` | populated owners → no raise |

Red→green confirmed: before the fix, the two fail-closed tests reported *"DID NOT RAISE
ApprovalEngineError"*; after the fix all pass. See `safety-regression-report.md`.

## 6. Success criteria (A-001)

- [x] Startup fails with empty `owner_ids` (clear error, no degraded mode).
- [x] Approvals fail with empty `owner_ids` (defense-in-depth).
- [x] Valid `owner_ids` behave unchanged (2 regression tests).

## 7. Deferred / observed (not changed — out of scope)

- **`bot.py:52-58` inline owner check** still uses the `if self.owner_ids and …` shape for the
  *ephemeral UX message*. It is **not** an authorization bypass: the authoritative decision is made
  by `evaluate_approval`, which now fails closed. Aligning the inline check for consistency is a
  cosmetic follow-up — **deferred** (would expand scope beyond the A-001 target).
