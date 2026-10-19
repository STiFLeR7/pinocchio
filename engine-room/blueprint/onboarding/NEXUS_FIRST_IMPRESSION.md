# NEXUS — First Impression

> Onboarding auditor's report. Nexus **v1.0.0** (commit `aa3e527`, tag `v1.0.0`). Read-only
> assessment; no code was changed. Every claim is backed by source; detailed evidence lives in
> `blueprint/onboarding/01`–`15`. Role: auditor / architect / operator — not feature developer.

---

## What Nexus actually is

Nexus is a **single-operator AI Orchestration Control Plane** — a long-lived, event-driven Python
service that coordinates tasks, human approvals, governed agent execution, research, and reporting
behind an immutable, event-sourced audit trail. Its thesis is held consistently in code and docs:
*orchestration is the product; conversation is a feature* (`docs/00_BRIEF.md:158-161`), and *AI
assists the system, it does not control it* (`docs/01_ARCHITECTURE.md:706-711`). Concretely it is a
FastAPI app (`nexus/api.py`) over a SQLite/WAL database (`nexus/database.py:100-106`), driven through
a Discord-first human interface, with a hard human-approval gate in front of all execution
(`nexus/execution/service.py:43-45`).

## What problem it solves

It de-fragments AI operations. Instead of chatting in one tool, tracking tasks in another, approving
actions manually, and running agents from terminals with no audit trail
(`docs/00_BRIEF.md:65-90`), Nexus centralizes that surface so one power user can delegate work,
approve privileged actions in Discord, run agents against allow-listed repos, and keep a complete,
recoverable record — under continuous human governance. The aspiration is a *trusted Chief of Staff*
(`docs/00_BRIEF.md:96-110`).

## Strongest architectural decisions

1. **The database-backed, un-bypassable approval gate.** Execution refuses to start without an
   `APPROVED` record, read from the DB (not Discord), with subprocess spawning confined to
   `nexus/execution/` (`execution/service.py:43-45`, `service-boundaries.md:103`). This is the single
   best decision in the system and it is genuinely enforced.
2. **Event sourcing with a derived ContextFrame.** State is an immutable append-only `audit_log`
   plus checkpoints; the working context is *recompiled* by replay, so corrupt history can't poison
   state (`memory/manager.py:28-101`, `models.py:184-199`). Recovery is structural, not bolted on.
3. **Transactional outbox for all outbound effects.** Events and messages are written in the same
   transaction as business state, then dispatched by background loops — a Discord outage can't lose
   an approval request (`memory/service.py:51-69`, `communication_outbox.py:79-243`).
4. **The 11-gate runtime governance with full audit-on-every-decision** (`governance.py:60-653`) —
   the most thorough, best-tested code in the repo (12 dedicated tests).

## Weakest architectural decisions

1. **Documenting a scheduler that was never built.** APScheduler is a dependency and the docs/ADRs
   lean on it for research, briefings, approval expiration, aggregation, and heartbeat sweeps — but
   **no scheduler exists in `nexus/`**; only three asyncio poll loops run (`api.py:114-127`). This
   single absence disables the entire autonomy story.
2. **`create_all` as the real schema source while Alembic migrations are incomplete and never
   tested** (`api.py:81-83`, `conftest.py:59`; 6 tables incl. base `repository_registry` have no
   migration). It makes migrations decorative and blocks the documented PostgreSQL path.
3. **Default sandbox = zero isolation** (`config.py:101`) with only a substring command blacklist as
   defense (`governance.py:621`) — a fragile security posture for a system that runs arbitrary
   commands.
4. **Letting the blueprint fall out of sync with the code** — STATUS/ROADMAP/README/CHANGELOG
   describe an earlier, smaller system, undermining the project's own "blueprint is authoritative"
   governance rule.

## Most valuable subsystem

**The approval + runtime governance layer** (`nexus/approvals/service.py` + `nexus/execution/
governance.py`). It is where Nexus's entire value proposition — *governed, auditable execution* —
actually lives, and it is excellently engineered and tested. Everything else is in service of getting
work safely through this gate.

## Highest operational risk

**Misconfigured approval authorization.** If `owner_ids` is empty (the config default,
`config.py:42`), the owner check is silently skipped (`approvals/service.py:94`, `bot.py:53`) and
*anyone* can approve privileged execution — collapsing the system's core guarantee. Combined with the
default no-isolation sandbox, this is the scenario that turns Nexus from "safe" to "dangerous"
fastest. (Closely followed by silent Discord approval-loss when the bot is down,
`service.py:80-82` ↔ `outbox.py:159`.)

## Highest technical-debt item

**The execution-timeout field-name bug** (`runners/claude.py:83`, `gemini.py:88`): runners read
`research_timeout_seconds`, which does not exist on `ExecutionConfig` (`config.py:83-86`), so every
CLI execution silently uses a 300-second fallback, ignoring the ADR-010 timeout tiers entirely. It is
small, high-impact, silent, and a perfect emblem of the broader "looks-configured-but-isn't" theme.
(The deepest *structural* debt is the absent scheduler; this is the highest-impact *bug*.)

## Most impressive implementation

**The communication outbox** (`nexus/gateway/communication_outbox.py`): lease-based concurrency with
`worker_id` guards, 5-minute lease reclamation of stuck items, exponential backoff with jitter,
bounded retries, dead-lettering, and audit records on both success and failure — verified by
dedicated concurrency and lease-expiry tests (`tests/unit/gateway/test_communication_outbox.py:235-274`).
This is genuinely production-grade distributed-systems code. (The irony, noted in `07`: the briefing
path defaults to a *synchronous flush* that bypasses this machinery.)

## Recommended next focus

Not new features — **close the doc/code gap and activate what's already built**:
1. **Tier-1 pre-pilot safety fixes** (small, evidence-clear): fix the timeout field name; fail-closed
   on empty `owner_ids`; make Discord send-failures observable; rotate the on-disk secrets;
   synchronize the blueprint. (`blueprint/onboarding/12`, I-01..I-05.)
2. **Wire APScheduler** (already a dependency) to bring the dormant research, briefing,
   approval-expiration, and metrics-aggregation engines to life, plus an orphan-execution monitor.
   This is the step that converts Nexus from an *attended console* into the *operational control
   plane* it is designed to be. (`12`, I-06..I-09.)

## Overall maturity score

**6.0 / 10.**

Rationale: The **core governed-execution kernel is an 8–9** — un-bypassable approval, thorough
audited governance, event-sourced recovery, and a production-grade outbox, all tested end-to-end.
But **operational maturity is a 3–4**: no scheduler, dormant autonomy engines, stub runtimes, a
silent timeout bug, default-off isolation, incomplete/untested migrations, and a blueprint that
misrepresents the system's own state. Averaged and weighted toward the fact that this is released and
"approved for pilot," **6.0** reflects *a genuinely strong, well-governed core that is honestly
pilot-ready only as an attended, single-operator console — with a clear, mostly-designed path to the
autonomous control plane it aspires to be.*

---

*Audit deliverables: `blueprint/onboarding/01-system-understanding.md` … `15-onboarding-summary.md`.
No source files were modified. Implementation work should be proposed only after this audit is
accepted, item-by-item, with evidence.*
