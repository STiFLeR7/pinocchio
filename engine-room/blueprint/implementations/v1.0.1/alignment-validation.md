# Nexus v1.0.1 "Alignment" — AP-101 Alignment Validation

> **Action Point:** AP-101 — Audit Validation
> **Status:** Complete · **Implementation in this AP:** NONE (validation only)
> **Method:** systematic-debugging Phase 1 (root-cause investigation, first-hand evidence).
> Every finding below was re-verified by reading current source at commit `aa3e527` (tag `v1.0.0`),
> independent of the prior onboarding subagent reports. Code citations are `file:line`.

---

## How to read this document

For each accepted finding (A-001…A-006) this provides the AP-101-mandated fields:
**Source Evidence · Root Cause · Risk · Impact · Fix Strategy · Validation Strategy**, plus a
**Constraint Trace** confirming the planned fix obeys the v1.0.1 operating constraints (no new
features / no redesign / every change traces to a finding).

**Validation verdicts:** `CONFIRMED` = reproduced from source; `CONFIRMED (runtime-proven)` =
also demonstrated by executing read-only code; `CONFIRMED + NUANCE` = true, with a material
clarification the fix must account for.

| Finding | Priority | Verdict |
|---|---|---|
| A-001 Fail-open owner authentication | P0 | **CONFIRMED** |
| A-002 Execution timeout mismatch | P0 | **CONFIRMED (runtime-proven)** |
| A-003 Missing scheduler layer | P1 | **CONFIRMED + NUANCE** |
| A-004 Documentation drift | P2 | **CONFIRMED** |
| A-005 Nexus simulated behaviors | P3 | **CONFIRMED** |
| A-006 Sandbox default host execution | P4 | **CONFIRMED + NUANCE** |

---

## A-001 — Fail-open owner authentication  (Priority 0) — CONFIRMED

### Source Evidence (first-hand)
- Config default is an **empty list**:
  `nexus/config.py:42` → `owner_ids: list[int] = Field(default_factory=list)`.
- The service normalizes to a list and **only checks when the list is truthy**:
  `nexus/approvals/service.py:35` → `self.owner_ids = [str(x) for x in (owner_ids or [])]`
  `nexus/approvals/service.py:94` → `if self.owner_ids and str(decided_by) not in self.owner_ids:`
  → when `owner_ids == []`, the `if self.owner_ids` short-circuits to `False`, so the
  unauthorized-raise is **never reached** and **any** `decided_by` is accepted.
- The Discord decision path has the same gate shape (validated in the onboarding audit at
  `nexus/communication/discord/bot.py:52-58`): an empty owner set disables the owner check there
  too.
- **Startup performs no owner-ids validation.** The FastAPI `lifespan` (`nexus/api.py:65-137`)
  wires logging, DB, git check, policy seeding, gateway, bot, orchestrator, and background loops —
  but never inspects `settings.discord.owner_ids`. `ApprovalService` is constructed **per-event,
  per-session inside the orchestrator**, not at startup, so there is currently no single place that
  asserts owner configuration before the system accepts work.

### Root Cause
Authorization is implemented as a *conditional* check (`if self.owner_ids and …`) whose guard
collapses to "allow all" on empty configuration — a classic **fail-open default**. The default
config value (`[]`) is itself a valid-but-unsafe state, and nothing at startup rejects it.

### Risk
**Critical / security.** A deployment that forgets to set `owner_ids` (the default) grants approval
authority — i.e. the authority to release governed execution against allow-listed repos — to *any*
Discord user or any caller of `evaluate_approval`. This silently nullifies the system's single most
important guarantee (human approval before execution).

### Impact
The approval gate (`execution/service.py:43-45`) still requires an `APPROVED` record, but **who may
create that record** becomes unrestricted. Effectively: unauthenticated privileged execution.

### Fix Strategy (AP-102 — design only here, no code in AP-101)
Trace: directly implements A-001 target ("fail closed; if no owner IDs configured, system startup
must fail").
1. Add a **startup validation gate** in `nexus/api.py` `lifespan` (after settings load, `api.py:68`)
   that raises a fatal startup error (e.g. `ConfigurationError`) when `settings.discord.owner_ids`
   is empty — preventing the app from reaching `yield`/serving.
2. As defense-in-depth (systematic-debugging `defense-in-depth`), make `ApprovalService` treat an
   empty `owner_ids` as **deny-all** rather than allow-all (invert the `if self.owner_ids` guard so
   an empty set raises on any decision). This keeps the service safe even if constructed outside the
   validated startup path (e.g. in scripts).
3. No change to the authorization *model* (owner-id allowlist) — constraint-compliant (no governance
   redesign).

### Validation Strategy
- **Unit:** `ApprovalService(owner_ids=[])` → `evaluate_approval(...)` raises (deny-all);
  `ApprovalService(owner_ids=[123])` → non-owner raises, owner succeeds (regression guard for
  existing behavior).
- **Startup:** an app/settings fixture with empty `owner_ids` causes `lifespan`/startup to raise;
  a populated `owner_ids` boots normally.
- **Regression:** existing approval tests (`tests/unit/approvals/test_service.py`) must still pass
  with owners configured.

### Constraint Trace
✅ Traces to A-001. ✅ No new feature (hardens existing auth). ✅ No architecture/governance redesign.

---

## A-002 — Execution timeout mismatch  (Priority 0) — CONFIRMED (runtime-proven)

### Source Evidence (first-hand + runtime proof)
- `ExecutionConfig` defines **no** `research_timeout_seconds` field:
  `nexus/config.py:83-88` → fields are `research_timeout(900)`, `gemini_timeout(1800)`,
  `claude_timeout(2700)`, `hard_limit(3600)`, `concurrency_retry_count`, `concurrency_retry_timeout`.
- Both CLI runners read the **non-existent** attribute with a 300 fallback:
  `nexus/execution/runners/claude.py:81-85` and `nexus/execution/runners/gemini.py:86-90`:
  ```python
  timeout = 300
  if self.settings and hasattr(self.settings, "execution") and self.settings.execution:
      t_val = getattr(self.settings.execution, "research_timeout_seconds", 300)  # always 300
      if isinstance(t_val, (int, float)):
          timeout = int(t_val)
  ```
- The 300s value is then the *only* enforced ceiling via `asyncio.wait_for(..., timeout=float(timeout))`
  (`claude.py:117-120`, `gemini.py:122-125`).
- **Runtime proof (read-only execution):**
  ```
  ExecutionConfig fields: ['research_timeout','gemini_timeout','claude_timeout','hard_limit',
                           'concurrency_retry_count','concurrency_retry_timeout']
  has research_timeout_seconds attr: False
  getattr(e,'research_timeout_seconds',300) => 300
  actual claude_timeout => 2700 | gemini_timeout => 1800 | hard_limit => 3600
  ```
- **Nexus path also wrong:** the Nexus `execute_command` tool hardcodes `timeout=300`
  (`nexus/execution/runners/nexus.py:118-123`), ignoring config entirely.
- **`hard_limit` is never enforced anywhere** — no runner reads `hard_limit`; the ADR-010 ceiling
  (3600s) is not applied as a cap.

### Root Cause
Two compounding defects: (1) a **wrong attribute name** (`research_timeout_seconds` vs the actual
`research_timeout`) that silently degrades to the 300s `getattr` default; and (2) a **conceptual
mapping error** — even the intended field is `research_timeout` for *all* CLI runners, rather than
each runner reading its ADR-010 per-runtime tier (`gemini_timeout`/`claude_timeout`). The
`hard_limit` ceiling was never wired.

### Risk
**High / correctness.** Every CLI execution is silently capped at 5 minutes regardless of
configuration or ADR-010, and there is no hard-limit safety ceiling.

### Impact
- Legitimate long-running Gemini (30m) / Claude (45m) tasks are killed at 5m with `exit_code=-1`
  and a misleading "exceeded timeout limit of 300s" message.
- ADR-010 ("Execution Timeouts & Heartbeat") is not honored at runtime — a documented decision
  contradicted by code.

### Fix Strategy (AP-102 — design only)
Trace: implements A-002 target ("ADR-approved timeout values must be honored; validate all runtime
execution paths").
1. Map each runtime to its ADR-010 field: Gemini → `gemini_timeout`; Claude → `claude_timeout`;
   research path → `research_timeout`; Nexus per-command → an appropriate config field (not a
   literal 300).
2. Apply `hard_limit` as an absolute ceiling: `effective = min(per_runtime_timeout, hard_limit)`.
3. Remove the broken `research_timeout_seconds` lookups in `claude.py`/`gemini.py` and the hardcoded
   `300` in `nexus.py:121`.
4. No change to the timeout *mechanism* (`asyncio.wait_for`) — constraint-compliant.

### Validation Strategy
- **Unit (per runner):** with a known `ExecutionConfig`, assert the `ExecutionStepRecord.timeout_threshold`
  and the `asyncio.wait_for` timeout equal the expected ADR-010 value (e.g. Claude → 2700, Gemini →
  1800), and that a configured value above `hard_limit` is clamped to 3600.
- **Path coverage:** explicit assertions for all three runtime execution paths (Claude.execute,
  Gemini.execute, Nexus.execute_command) — satisfies "validate all runtime execution paths."
- **Runtime regression:** re-run the read-only `getattr` proof inverted — the new code must read an
  existing field (no `hasattr == False`).

### Constraint Trace
✅ Traces to A-002. ✅ No new feature (corrects existing field wiring). ✅ Honors ADR-010 (no
redesign).

---

## A-003 — Missing scheduler layer  (Priority 1) — CONFIRMED + NUANCE

### Source Evidence (first-hand)
- APScheduler **is installed**: `pyproject.toml:17` (`apscheduler>=3.10.0`), resolved to 3.11.2
  (`uv.lock:182-190`).
- **Zero scheduler usage in source:** a repo-wide search for
  `apscheduler|AsyncIOScheduler|BackgroundScheduler|add_job|CronTrigger|IntervalTrigger` over
  `nexus/` returns **no matches**.
- `nexus/scheduling/` contains only `__init__.py` and `orchestrator.py` — the latter is an
  **event-driven** `WorkflowOrchestrator`, not a time scheduler. There is no `scheduler.py`.
- Only background timers are three `asyncio` poll loops in `nexus/api.py:114-127`
  (outbox 2s, comm-outbox 2s, metrics-flush 5s) — none are cron/interval scheduled jobs.
- All four target engine entrypoints **exist but have no production caller** (callers only in
  `tests/` and `scripts/`):
  - `nexus/intelligence/research.py:218` `execute_research_run`
  - `nexus/intelligence/briefing.py:74` `generate_and_dispatch_briefing`
  - `nexus/core/metrics.py:142` `run_aggregation_and_retention`
  - `nexus/approvals/service.py:184` `sweep_expired_approvals`

### Root Cause
The autonomy engines were built (Phases 2–3) but the **scheduling layer that drives them was never
implemented** — the package name `scheduling/` was repurposed for the event orchestrator, leaving
no home for time-based triggers.

### NUANCE (must be carried into AP-103 design)
The A-003 target lists **six** required jobs. Four map to existing functions (above). **Two have no
existing implementation:**
- **Outbox Health Monitoring** — no `*health*`/`*monitor*` function exists in `nexus/gateway/`.
- **Checkpoint Health Monitoring** — no such function exists in `nexus/memory/`.

These two jobs require **new monitoring code**, which sits close to the v1.0.1 constraint "No new
features." Recommended framing for AP-103: scope them as **read-only health *observation* of
existing subsystems** (e.g. counting `system_outbox` dead-letter/backlog rows; flagging stale
`last_heartbeat`/checkpoint age) that emit metrics/audit events — *operational completeness*, not
new product capability. This must be explicitly justified in `scheduler-design.md` and approved
before implementation (the work sequence already gates AP-103 implementation on design approval).

### Risk
**Med / operability.** Nexus cannot operate unattended: research, briefings, approval expiration,
and metrics aggregation never run autonomously. Tasks can strand in `BLOCKED` indefinitely (see
A-001/expiration), and the metrics aggregate table stays empty / raw rows are never purged.

### Impact
The "operational control plane" claim is unmet: the system is an attended console. This is the
single largest gap between architectural intent and behavior.

### Fix Strategy (AP-103 — DESIGN FIRST, then implement after approval)
Trace: implements A-003 target. Per the work sequence, AP-103 produces `scheduler-design.md` +
`scheduler-event-map.md` and implements **only after design approval**. Design principles required
by the brief: no architectural boundary violations; no direct coupling; clean integration with
Research/Briefing/Metrics/Outbox/Governance. Likely shape: an `AsyncIOScheduler` started in the
`lifespan`, scheduling thin job wrappers that each open their own `get_session` and invoke the
existing engine entrypoints — mirroring the existing asyncio-loop pattern rather than introducing a
new coupling style.

### Validation Strategy
- **Design gate:** `scheduler-design.md` + `scheduler-event-map.md` reviewed/approved (no
  implementation before approval).
- **Post-implementation:** unit tests that each job wrapper invokes its engine entrypoint with a
  valid session; an integration test that the scheduler registers all six jobs at startup and that
  triggering each produces the expected side effect (finding row / briefing row / expired sweep /
  aggregate row / health metric).

### Constraint Trace
✅ Traces to A-003. ⚠️ Two jobs (outbox/checkpoint health) require new monitoring code — flagged for
explicit AP-103 design approval to stay within "no new features." ✅ No redesign of the engines
themselves.

---

## A-004 — Documentation drift  (Priority 2) — CONFIRMED

### Source Evidence (first-hand)
- **`README.md`** is stale on multiple axes:
  - badges: `status-pre--alpha`, `version-0.1.0`, `python-3.11%2B` (`README.md:5-7`).
  - Development Status table marks **all** phases including Phase 0/1 as `🔲 Pending`
    (`README.md:144-153`) — contradicted by completed Phase 0/1 and shipped Phase 2/3.
  - "Getting Started … Nexus is in pre-alpha. Setup instructions will be published when Phase 0 is
    complete." (`README.md:161`).
- **`STATUS.md`** (verified in onboarding) dated 2026-06-20, "Phase 1 Completed," Phases 2–7 "Not
  Started" (`blueprint/STATUS.md:58-68`).
- **`ROADMAP.md`** marks Phase 2 "🔲 Not Started" et seq. (`blueprint/ROADMAP.md:115-275`).
- Reality (git): Phases 2–3 shipped (`8c31e10`, `23c5a02`…`4566020`), tagged `v1.0.0` (`aa3e527`).
- Corroborating drift (from accepted audit, for completeness in AP-104): `CHANGELOG.md` stops at
  `0.0.1`; `pyproject.toml:3` version `0.1.0`; README/docs Python "3.11+" vs `requires-python>=3.12`.

### Root Cause
Project-state documents were not updated as Phases 2–3 shipped and the v1.0.0 release was tagged —
the blueprint-synchronization discipline (Operating Rule 9) lapsed. The *cause* is process, not
code.

### Risk
**Med (trust/governance).** The blueprint is designated authoritative project memory, yet it
misrepresents the system. New operators/developers and the audit process itself can be misled.

### Impact
Onboarding friction and governance-integrity erosion. (No runtime impact.)

### Fix Strategy (AP-104 — design/scope only here)
Trace: implements A-004 target ("all project state documents must accurately represent Nexus
v1.0.0; blueprint memory must be authoritative"). Update `README.md`, `ROADMAP.md`, `STATUS.md`,
release/phase history, architecture-status, and blueprint references to reflect actual v1.0.0 state
**plus** the in-progress v1.0.1 alignment work. This is documentation only — no code, no new claims
beyond what the accepted audit and code substantiate.

### Validation Strategy
- **Cross-check:** every status claim in the updated docs must cite either a git commit/tag, a code
  `file:line`, or an accepted audit finding (`documentation-alignment-report.md` records the
  mapping).
- **No-overclaim guard:** docs must mark built-but-dormant subsystems (research/briefing/scheduler)
  honestly per the audit, not as fully operational.

### Constraint Trace
✅ Traces to A-004. ✅ Documentation only (no feature/architecture change). ✅ Synchronizes blueprint
(Operating Rule 7).

---

## A-005 — Nexus simulated behaviors  (Priority 3) — CONFIRMED

### Source Evidence (first-hand, `nexus/execution/runners/nexus.py`)
- **Production import of a test double:** `from unittest.mock import AsyncMock` (`nexus.py:7`).
- **Simulation branch in the live loop:** `nexus.py:184-209` — `is_mocked` is true when there is
  no OpenRouter client, when `self.openrouter_client.complete` is an `AsyncMock`, or when the
  api_key contains `"test-key"`; in that branch the action sequence is hardcoded
  (search → write `mcp_report.md` → finish).
- **Hardcoded plan:** `nexus.py:145-149`.
- **Canned `web_search`:** returns fixed MCP text for any query containing "mcp", else "No results"
  (`nexus.py:76-86`) — no real search backend.
- **Hardcoded tool timeout:** `execute_command` uses `timeout=300` literal (`nexus.py:118-123`)
  (also an A-002 path).
- **No-op terminate:** `async def terminate(self): pass` (`nexus.py:310-312`) — a runaway loop
  cannot be force-stopped.
- **Path-containment bypass:** `write_file` writes to arbitrary `os.path.abspath(path)`
  (`nexus.py:96-105`), outside the governance repo allowlist.
- **A real LLM path does exist** (`nexus.py:210-232`), so Nexus is *partly* real.

### Root Cause
Nexus was delivered as a scaffold with embedded test simulation so it could pass E2E/unit flows
without a live model or search backend; the simulation shims (`AsyncMock`, canned search, hardcoded
plan) were left in the production module rather than isolated to tests.

### Risk
**Med (honesty/operational).** Nexus appears to be a working autonomous agent but, under common
configurations, executes a scripted simulation. Behavior is non-obvious and not production-faithful.

### Impact
Any reliance on Nexus for real autonomous work is unsafe today; its true capability boundary is
undocumented.

### Fix Strategy (AP-105 — AUDIT ONLY; do not replace anything)
Trace: implements A-005 target ("produce a complete reality audit; separate Implemented / Partially
Implemented / Stubbed / Mocked / Future; do not replace anything yet"). AP-105 deliverable is
`nexus-reality-audit.md` — an evidence-classified inventory of every Nexus capability. **No code
changes** in v1.0.1 for Nexus beyond the A-002 timeout correction (which is a shared runtime path,
already traced to A-002, not a Nexus redesign).

### Validation Strategy
- The audit is validated by completeness + evidence: every method/tool/branch in `nexus.py` is
  classified with a `file:line` citation and a category. No assumptions; quotes required.

### Constraint Trace
✅ Traces to A-005. ✅ Evidence-only (no replacement). ✅ The only Nexus code touched in v1.0.1 is
the A-002 timeout path.

---

## A-006 — Sandbox default may execute on host  (Priority 4) — CONFIRMED + NUANCE

### Source Evidence (first-hand)
- **Default config disables isolation:** `nexus/config.py:101-102` → `enabled: bool = False`,
  `provider: str = "local"`.
- **Disabled path resolves to host execution:** `nexus/execution/sandbox/manager.py:44-45` →
  `if not cfg.enabled: return LocalSandboxProvider()`.
- **Local provider runs directly on host:** `nexus/execution/sandbox/provider.py:96-101` →
  `asyncio.create_subprocess_shell(command, ..., cwd=cwd)` with no namespace/container isolation.
- **Docker path is real isolation:** `provider.py:133-175` → `docker run --cpus --memory --network
  -v host:/workspace[:ro] -w /workspace <image> sh -c <command>`.
- **Mock path:** keyword-simulated results (`provider.py:210-246`).

### NUANCE (positive findings to record, not just risks)
1. **Failure behavior fails closed, not to host.** If Docker is enabled but `docker` is missing or
   `spawn` fails, `manager.execute` audits `sandbox.failure` and **re-raises** (`manager.py:120,
   172-179`); `_resolve_provider` does **not** fall back from Docker to Local on error
   (`manager.py:47-53`). So an enabled-Docker deployment does **not** silently degrade to host
   execution — it fails the execution. This is correct and should be preserved.
2. **Real host-exposure risk is confined to the default/disabled configuration**, where the only
   barrier is the governance command blacklist (substring-based, `governance.py:621`).
3. `terminate()` on `LocalSandboxProvider` is implemented (`provider.py:115-124`), but
   `SandboxProcess.terminate` fires a detached task (`provider.py:45-48`) — not awaited (observation
   for the report, not an A-006 target).

### Root Cause
The safe-by-default principle was inverted for developer convenience: `enabled=False` ships as the
default, making "no isolation / run on host" the out-of-the-box behavior.

### Risk
**Med→High in default config (configuration-dependent).** Out of the box, approved commands run on
the host; combined with a bypassable substring blacklist this is the host-compromise surface noted
in the audit (R-02).

### Impact
Operators may run Nexus believing execution is sandboxed when, by default, it is not.

### Fix Strategy (AP-? — A-006 target is a CONFIGURATION AUDIT, not a code change)
Trace: implements A-006 target ("perform configuration audit; validate Docker-enabled path,
Docker-disabled path, failure behavior, fallback behavior, host-exposure risks"). The accepted
finding asks for a **documented configuration audit** (the four paths + host-exposure analysis),
**not** a behavior change. Any default-flip (e.g. `enabled=True`) would be a behavior/operability
change and must be raised separately, not assumed. This AP-101 entry records the audit substance;
the formal write-up belongs in the AP that the team assigns to A-006 (none is in the AP-101…AP-105
required sequence, so A-006 currently terminates at "audited and understood" unless an AP is added).

### Validation Strategy
- **Path matrix (documented, evidence-backed):**
  | Config | Provider resolved | Isolation | Failure behavior |
  |---|---|---|---|
  | `enabled=False` (default) | Local | none (host) | host process errors surface normally |
  | `enabled=True, provider=docker` | Docker | cgroup cpu/mem + net ns + volume mount | spawn failure → audit + **re-raise** (no host fallback) |
  | `enabled=True, provider=mock` | Mock | simulated | keyword-driven |
  | `enabled=True, provider=<other>` | Local (else-branch) | none (host) | ⚠ note: an unknown provider name silently falls back to Local/host (`manager.py:52-53`) |
- The unknown-provider→Local fallback (`manager.py:52-53`) is a **host-exposure footgun** worth
  recording: a typo in `provider` yields host execution despite `enabled=True`.

### Constraint Trace
✅ Traces to A-006. ✅ Audit/documentation only (no default change without separate approval).
✅ No redesign.

---

## Cross-finding observations (for sequencing)

1. **A-002 spans Nexus (A-005).** The Nexus `execute_command` hardcoded `300` is both an A-002
   path and an A-005 datum. v1.0.1 will correct it under A-002 (shared runtime path), while A-005
   only *documents* it — no conflict, but the AP-102 and AP-105 reports must cross-reference.
2. **A-001 and A-003 interact.** Fixing expiration scheduling (A-003) reduces the blast radius of
   stranded `BLOCKED` tasks, but does **not** substitute for the A-001 fail-closed fix.
3. **Two A-003 jobs need new code** (outbox/checkpoint health) — the only place in v1.0.1 where the
   "no new features" constraint is genuinely tested. Gate at AP-103 design approval.
4. **A-006's accepted target is an audit, not a fix** — recorded here as understood; no code change
   is authorized by the finding as written.

## AP-101 outcome

All six accepted findings are **independently re-validated against current source** with first-hand
evidence (A-002 additionally runtime-proven). No implementation was performed. Fix and validation
strategies are defined and constraint-traced. Ready to proceed to **AP-102 (Critical Safety Fixes:
A-001, A-002)** upon authorization.
