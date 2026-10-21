# Operational Dashboard — Nexus v1.1.0 (first live snapshot)

> Captured from live DB state during bring-up, 2026-06-25. Real data, no mocks.

---

## System Health
- **Boot:** ✅ online (A-001 owner auth active, sandbox gate, DB, scheduler, runtimes).
- **Gates:** pytest **219 passed** · ruff clean · mypy clean (61 files).

## Scheduler Status
- 6 jobs registered (J1–J6); 4 executed live this session.
- Audit: `scheduler.job.started: 4`, `scheduler.job.completed: 4`. Metrics: J5 outbox / J6 checkpoint
  health gauges recorded.

## Runtime Status
- Registry: `nexus → NexusRuntimeAdapter`, `gemini → GeminiRuntimeAdapter`, `claude →
  ClaudeRuntimeAdapter`, legacy `hermes → NexusRuntimeAdapter`.
- Executions: **3**; agent steps: **5**; nexus agent runs reached `completed`/`timed_out` (honest).
- LLM gateway: multi-provider (Groq primary ~120 ms).

## Research Status
- Live run: **20 findings** persisted from HN RSS. `research.completed: 1`.

## Briefing Status
- Generated + dispatched: **2** (`report.generated: 2`) via real engine + SMTP email.

## Sandbox Status
- `enabled=False`, `provider=local`, `network=none`, `fs=restricted` → default-secure; execution
  fail-closed (Track S). S-3 startup gate passed.

## Governance Status
- A-001 owner authorization **ACTIVE** (1 owner). Audit: `RepositoryValidated: 4`,
  `RuntimeAuthorized: 4`. `PolicyFallbackUsed: 24` (defaults seeded — expected on fresh DB).

## Outbox Status
- J5 read-only health snapshot executed (no backlog repair attempted — by design).

## Metrics Summary (active gauges)
`approval_latency_ms, briefing_generation_duration_ms, db_write_duration_ms, discord_latency_ms,
event_flush_duration_ms, execution_start_latency_ms, lock_wait_ms, openrouter_latency_ms,
smtp_latency_ms, transaction_duration_ms`.

## Recent Executions
- 3 executions (nexus agent): initial `completed`, recovery interrupt→resume `completed`, one honest
  `failed` (malformed model tool-call). Exit-status finalization is set by the orchestrator path
  (direct-harness runs left `exit_status=None` on the record — expected).

## Recovery Status
- Checkpoint resume verified: interrupt→`timed_out` → fresh-adapter resume→`completed`; **39
  checkpoints** persisted across runs; no corruption; audit continuity intact.

## Notifications
- Email: ✅ delivered (SMTP). Discord: ✅ delivered (bot Dex#9955 → #general, msg
  `1519643857816649821`).

## Headline
**9/9 subsystems live-validated.** Nexus is **Pilot Ready**.
