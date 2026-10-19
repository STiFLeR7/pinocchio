# 14 — First-Week Developer Guide

> Read-only audit output. How to navigate, build, test, and safely extend Nexus v1.0.0.
> ⚠ marks audit-found traps. Honors the Operating Rules: understand before changing.

---

## Day 1 — Orient

**Read in this order:** `01-system-understanding.md` → `02-architecture-map.md` → the subsystem map
for the area you'll touch (`03`–`08`). Then read the actual source — it's small (~8,800 LOC across
`nexus/`).

**The mental model that matters most:** Nexus is **event-driven**. Components rarely call each other
directly; they `publish`/`subscribe` on the in-process `EventGateway` (`gateway/gateway.py`) and
communicate durably through DB outbox tables. To follow a flow, trace events, not the call stack
(see the spine diagram in `02-architecture-map.md` §3).

**Package → responsibility:**
```
nexus/core/         enums(types), exceptions, health, metrics, policy_defaults, events
nexus/memory/       ORM models, MemoryService (audit+outbox+checkpoint), TaskService, PolicyService, ContextCompiler
nexus/gateway/      EventGateway (bus) + two outboxes (system_events, system_outbox)
nexus/scheduling/   WorkflowOrchestrator (event-driven; NOT a scheduler)
nexus/approvals/    ApprovalService (the approval gate)
nexus/execution/    service, governance (11-gate), runners (claude/gemini/nexus), sandbox
nexus/intelligence/ openrouter, research, briefing, summary
nexus/communication/ discord (bot/service), email (service)
nexus/api.py        FastAPI app + lifespan wiring (read this to see what actually boots)
```

## Day 2 — Build & test

```bash
uv sync                       # or pip install -e ".[dev]"
uv run pytest                 # 110 tests; ⚠ must run inside the venv (see trap D-1)
uv run pytest tests/unit/     # fast unit layer
uv run pytest --cov=nexus --cov-report=html && start htmlcov/index.html
uv run ruff check nexus/ tests/
uv run mypy nexus/ --ignore-missing-imports
```

**CI** (`.github/workflows/ci.yml`): one job on push/PR to main/master runs `uv sync` → ruff → mypy
(`strict=true`) → pytest+coverage. All three gate merges. ⚠ No coverage threshold is enforced
(`ci.yml:42`).

⚠ **Trap D-1:** `python -m pytest --collect-only` fails outside `.venv` with
`ModuleNotFoundError: discord` because `tests/conftest.py:16` imports `nexus/api.py` →
`discord/bot.py`. Always run tests inside the environment.

⚠ **Trap D-2:** Tests build schema via `Base.metadata.create_all` (`conftest.py:59`), **not**
Alembic. A broken migration passes all tests but fails a real `alembic upgrade head`. If you change
the schema, add/verify a migration manually and consider a round-trip test.

⚠ **Trap D-3:** Two Ruff configs exist; `ruff.toml` wins and `[tool.ruff]` in `pyproject.toml` is
dead (`ruff.toml` vs `pyproject.toml:55-60`). Edit `ruff.toml`.

## Day 3 — Test coverage reality

110 tests (`pytest --collect-only`). **Well covered:** governance (12 tests,
`tests/unit/execution/test_governance.py`), runners, sandbox, P0 hardening, state machines,
metrics persistence, comm outbox concurrency, research/briefing units, approvals.
**Not covered (write tests here before extending):** Discord bot/service, Email service, the
`WorkflowOrchestrator` (only indirectly via e2e), OpenRouter client (always mocked), Summary,
`run_git_startup_validation`, and any Alembic round-trip.

## Day 4 — Extending safely (respect the invariants)

**Architectural rules enforced in code — do not break:**
- **Approval gate:** never add a code path that spawns execution without `check_approval_gate`
  (`execution/service.py:43-45`). Subprocess spawning stays in `nexus/execution/`
  (`service-boundaries.md:103`).
- **Layered imports:** lower layers must not import higher (`ADR-phase1-foundation.md:50-62`).
- **Intelligence is read-only toward orchestration:** research/briefing/summary must not mutate
  task/approval/execution state or spawn execution (`docs/01_ARCHITECTURE.md:398-405`).
- **Audit log is immutable & append-only** (`AuditMixin`, `models.py:184-199`) — never UPDATE/DELETE.
- **Outbox writes are transactional** — write the outbox row in the *same session* as the business
  state (`memory/service.py:51-69`).

**To add a runtime:** create `nexus/execution/runners/<name>.py`, subclass `CLIRuntimeAdapter` or
`AgentRuntimeAdapter`, decorate with `@runtime_registry.register("<name>")`, match the 5-arg
constructor (`runners/__init__.py:58-64`). The orchestrator needs no changes
(`ADR-runtime-selection.md:44`). ⚠ Use real config timeout fields (don't copy the
`research_timeout_seconds` bug, `claude.py:83`).

**To add a scheduled job:** ⚠ there is currently **no scheduler** to add to. Wiring APScheduler
(already a dependency) is itself a feature, not an extension point (see `12`, I-06). Until then,
new periodic work follows the `asyncio` poll-loop pattern in `api.py:114-127`.

**To add an event:** add to `EventType` (`core/types.py:56-102`), publish via the gateway and/or
write through `MemoryService.log_event`, and add a subscriber in `orchestrator.register_listeners`
(`orchestrator.py:46-52`). ⚠ Keep `event-model.md` in sync (it's already stale).

## Day 5 — Gotchas inventory (read before your first PR)

- ⚠ **Timeout field-name bug** (`runners/claude.py:83`, `gemini.py:88`) — don't propagate it.
- ⚠ **`AsyncMock` in production Nexus** (`nexus.py:7,186`) — if you touch Nexus, inject a test
  double instead.
- ⚠ **Dead code:** `sandbox/collector.py`, `briefing._deliver_discord`, the selection
  description-prefix heuristic — don't build on them.
- ⚠ **Discord adapter holds business logic + DB access** (`bot.py:237-279`) — the deferred Command
  Bus (`ADR-command-bus-evaluation.md`) is the intended fix; don't add more.
- ⚠ **`create_all` vs Alembic divergence** — the source of schema truth is the ORM, not migrations.
- ⚠ **Version/Python-floor incoherence** — `pyproject.toml` says 0.1.0 / py3.12; docs say 3.11+.

## Developer quick reference

| Task | Command |
|---|---|
| Install | `uv sync` |
| Run app | `python -m nexus` |
| Test | `uv run pytest` (in venv) |
| Lint | `uv run ruff check nexus/ tests/` (config: `ruff.toml`) |
| Types | `uv run mypy nexus/ --ignore-missing-imports` |
| New migration | `alembic revision --autogenerate -m "..."` then verify manually |
| Trace a flow | follow `EventType` publish/subscribe, not the call stack |

**The one principle to carry:** Nexus's value is its **governance + auditability**. Any change must
preserve the un-bypassable approval gate, the immutable audit log, and the transactional outbox. When
in doubt, add a test that proves the invariant still holds.
