# A-002 — Runtime Timeout Validation (Honor ADR-010 + Enforce Hard Limit)

> **Release:** Nexus v1.0.1 "Alignment" · **AP:** AP-102 · **Finding:** A-002 (Priority 0)
> **Type:** Root-cause correctness fix (TDD) · **Status:** ✅ Implemented & validated

---

## 1. Defect (v1.0.0)

All runtime execution paths used the wrong timeout:

- Claude & Gemini read `getattr(self.settings.execution, "research_timeout_seconds", 300)`
  (`claude.py:83`, `gemini.py:88`). `ExecutionConfig` has **no** `research_timeout_seconds` field
  (`config.py:83-88`), so the `getattr` **always returned 300s**, ignoring configuration and the
  ADR-010 tiers. Runtime-proven in AP-101: `hasattr(ExecutionConfig(), 'research_timeout_seconds')
  == False`.
- Nexus' `execute_command` tool hardcoded `timeout=300` (`nexus.py:121`).
- `hard_limit` (ADR-010 ceiling, 3600s) was **never enforced** anywhere.

Net effect: every execution silently capped at 5 minutes, with no hard ceiling.

## 2. Target (accepted finding)

All runtime adapters honor configured limits; `hard_limit` is impossible to exceed; verify Claude,
Gemini, and Nexus paths.

## 3. Implementation

### Shared resolver (`nexus/execution/runners/base.py`)
New pure helper `resolve_execution_timeout(settings, field_name, *, default=300)`:
- reads `settings.execution.<field_name>`;
- falls back to `default` when settings/field are absent or non-numeric (preserves behavior when no
  settings are injected, e.g. lightweight tests);
- **clamps to `settings.execution.hard_limit`** via `min(...)` when configured — so the hard limit
  can never be exceeded regardless of misconfiguration.

### Per-runtime mapping (the "verify runtime mapping" requirement)

| Runtime | File:line (before) | Field used (after) | Default value |
|---|---|---|---|
| Claude (CLI) | `claude.py:83` (`research_timeout_seconds`→300) | `claude_timeout` | 2700s |
| Gemini (CLI) | `gemini.py:88` (`research_timeout_seconds`→300) | `gemini_timeout` | 1800s |
| Nexus (agent `execute_command`) | `nexus.py:121` (hardcoded 300) | `research_timeout` | 900s |

**Nexus mapping rationale:** `ExecutionConfig` has no dedicated `nexus_timeout` field, and adding
one would be a config/feature addition outside AP-102's "no new features" constraint. Nexus is the
autonomous research/planning agent, and ADR-010's agent/research tier is `research_timeout` (15 min)
— the semantically correct existing field. Each per-command sandbox run is clamped by `hard_limit`.
This honors "Nexus timeout respected" using configured values, adds **zero new fields**, and can be
revisited if a dedicated Nexus tier is ever introduced (deferred, documented).

### Removed
- The broken `research_timeout_seconds` lookups in `claude.py` / `gemini.py`.
- The hardcoded `timeout=300` in `nexus.py` `execute_command`.

The enforcement mechanism (`asyncio.wait_for(..., timeout=float(timeout))` in the CLI runners; the
`SandboxManager.execute(timeout=...)` argument for Nexus) is unchanged — only the *value* is now
correct. `ExecutionStepRecord.timeout_threshold` now records the true per-runtime timeout.

## 4. Tests (TDD) — `tests/unit/execution/test_timeout_resolution.py` (10)

Resolver unit tests:
| Test | Asserts |
|---|---|
| `test_resolve_claude_timeout` | `claude_timeout` → 2700 |
| `test_resolve_gemini_timeout` | `gemini_timeout` → 1800 |
| `test_resolve_research_timeout_for_nexus` | `research_timeout` → 900 |
| `test_hard_limit_is_impossible_to_exceed` | `claude_timeout=99999, hard_limit=3600` → 3600 |
| `test_unknown_field_falls_back_to_default` | old broken name resolves safely to 300 (no crash) |
| `test_none_settings_returns_default` | `None` settings → 300 |

Per-runtime behavioral tests (timeout actually applied):
| Test | Asserts |
|---|---|
| `test_claude_execute_uses_claude_timeout` | step.timeout_threshold == `claude_timeout` (2700) |
| `test_gemini_execute_uses_gemini_timeout` | step.timeout_threshold == `gemini_timeout` (1800) |
| `test_claude_execute_clamps_to_hard_limit` | `claude_timeout=99999, hard_limit=120` → step threshold 120 |
| `test_nexus_execute_command_uses_research_timeout` | sandbox called with `research_timeout` (900), via monkeypatched `SandboxManager.execute` |

Red→green confirmed (module failed import before the resolver existed; all 10 pass after). See
`safety-regression-report.md`.

## 5. Success criteria (A-002)

- [x] Configured timeout respected (Claude 2700 / Gemini 1800 / Nexus 900 behavioral tests).
- [x] Hard limit respected / impossible to exceed (resolver + behavioral clamp tests).
- [x] Claude / Gemini / Nexus paths each verified.
- [x] Regression tests included; existing runner tests still pass (settings-less path → 300 default,
      unchanged).

## 6. Deferred / observed (not changed — out of scope)

- **No `nexus_timeout` config field** added (would be a config addition). Nexus uses
  `research_timeout`; introducing a dedicated tier is **deferred**.
- The CLI runners still mark a timed-out step `COMPLETED` with `exit_code=-1` (audit finding TD-21).
  That is a separate accepted item, **not** in AP-102 scope — **deferred**.
