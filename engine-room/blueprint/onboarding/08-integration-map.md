# 08 — Integration Map (Architecture Review: Discord, Email, OpenRouter / Research / Briefing)

> Read-only audit of `nexus/communication/*` and `nexus/intelligence/*`. Evidence cited as
> `file:line`.

---

## A. Discord  (`nexus/communication/discord/`)

**Purpose** — Primary human interface: task entry (slash commands), approval cards/buttons, and
notification delivery.

**Wiring** — `NexusBot` is created in the FastAPI lifespan and started only if a real token is
configured (placeholder `"YOUR_DISCORD_BOT_TOKEN"` is skipped, `api.py:101-135`). Intents:
message_content + guilds; prefix `/`; slash commands synced in `setup_hook` (`bot.py:141-166`).

**Slash commands** — `task_create`, `task_list`, `task_status` (`bot.py:225-328`). `task_create`
creates a task then transitions it to `QUEUED` (`bot.py:242-249`).

**Approval cards** — `send_approval_request` posts an embed to `#approvals` with an `ApprovalView`
(persistent `timeout=None`, Approve/Reject buttons, `service.py:84-113`, `bot.py:104-128`).
**Owner authorization** in `handle_decision`: non-owners get an ephemeral "Unauthorized" reply
(`bot.py:52-58`); on success it disables buttons, calls `ApprovalService.evaluate_approval`, and
edits the embed (`bot.py:60-98`).

**⚠ Issues**:
- **No reconnect handling** — no `on_disconnect`/`on_resumed`/`on_error` anywhere; relies on
  discord.py auto-reconnect + outbox redelivery.
- **Business logic in the adapter** — `bot.py` directly instantiates `MemoryService`/`TaskService`,
  runs SQLAlchemy queries (`bot.py:237-249,270-279`), and `ApprovalView.handle_decision` runs DB
  sessions + calls `ApprovalService` (`bot.py:70-98`). This violates the "adapters contain no
  business logic" principle (`discord-integration-design.md:8-12`).
- **Channel fallback** — `get_channel_by_config` falls back to the *first text channel* if config is
  missing (`bot.py:213-215`) — sensitive content (approvals) could land anywhere.
- **ADR-008 non-compliance** — no `DiscordAuthGuard` class; unauthorized attempts are **not logged
  or audited**, and a visible ephemeral reply is sent instead of the mandated silent discard
  (`ADR-008:35-57` vs `bot.py:52-57`).

---

## B. Email  (`nexus/communication/email/service.py`)

**Purpose** — SMTP delivery of briefings via `aiosmtplib`. `send_briefing_email(subject, text, html)`
builds a `MIMEMultipart("alternative")`, uses implicit SSL on port 465 else STARTTLS, logs in only
if credentials present (`service.py:23-81`).

**Failure handling** — Missing `smtp_host` → log + silent return; SMTP exceptions are **re-raised**
(`service.py:79-81`), so the comm-outbox retry/backoff/dead-letter engages correctly.

**⚠ Issues**:
- **No templates** — `templates/email/` contains only `.gitkeep`; HTML is built upstream in
  `briefing.py` as hand-rolled f-strings. Jinja2 is a dependency (`pyproject.toml:20`) but unused.
- **ADR-007 non-compliance** — ADR-007 mandates an `EmailProvider` protocol "from day one" so
  providers (Gmail SMTP → Resend → SES) are swappable (`ADR-007:11-13,44-68`). No protocol exists;
  `EmailService` talks to `aiosmtplib` directly; the `provider` config field is never read.
- **Untested** — no test for the email service (the planned `test_email_service.py` was never
  created, `DEVELOPMENT.md:199`).

---

## C. OpenRouter / Model Router  (`nexus/intelligence/openrouter.py`)

**Purpose** — Single gateway to OpenRouter `/chat/completions` with sequential model fallback.
`complete(prompt, system_prompt)` (`openrouter.py:27`).

**Fallback chain** — `[primary_model, *fallback_models]` (`:34`). ⚠ Two **divergent config sources**:
Python defaults are paid `google/gemini-2.5-pro` → `anthropic/claude-sonnet-4` →
`google/gemini-2.5-flash` (`config.py:63-69`); the YAML example defaults to free
Nemotron/DeepSeek/Llama (`settings.example.yaml:58-62`). Neither matches the architecture doc's
Nemotron→OwlAlpha→DeepSeek chain (`docs/01_ARCHITECTURE.md:440-466`).

**⚠ No circuit breaker, no retry/backoff** — each model is tried once in order; on any exception it
logs and falls through to the next (`:45-95`); all-fail → `ModelRouterError` (`:98-100`). The 30s
timeout is a **total budget across all models**, not per-model (`:44`) — a slow primary starves the
fallbacks. No `max_tokens` cap (cost/latency runaway risk). `temperature=0.2` hardcoded.

---

## D. Research Engine  (`nexus/intelligence/research.py`) — built, not triggered

**Purpose** — Crawl RSS/Atom feeds → normalize → dedup vs DB → LLM-summarize+score+tag → persist
`ResearchFindingRecord` → checkpoint after every finding → resumable.

**Reality vs design** — Only an **RSS/Atom provider** exists (`research.py:86-195`); the
search-API/arXiv/scraper providers in `research-workflow-design.md:53-56` are doc-only. The
`ResearchProvider` ABC + `register_provider` (`:214-216`) is the real extension seam.
**No scheduler invokes `execute_research_run`** — only tests and `resume_research_run` call it; and
`RESEARCH_COMPLETED` has no subscriber. So research is fully implemented but **dormant**.

**Failure modes** — Broken feeds are swallowed and return `[]` with no per-feed event
(`:104-112`); LLM summarize failure falls back to score 0 + generic tags but leaves `summary` empty
(`:587-595`); persist/summarize logic is **triplicated** across three methods (drift risk).

---

## E. Briefing Engine  (`nexus/intelligence/briefing.py`) — built, not triggered

**Purpose** — Aggregate 24h operational state (research findings, open tasks, pending approvals,
failed/all executions, policy violations, checkpoint recoveries, health, metrics) → render markdown
+ HTML → persist `BriefingRecord` → deliver via memory/Discord/email through the comm outbox.

**Reality vs design** — **No LLM synthesis** (the doc's "OpenRouter LLM synthesis" stage does not
exist, `daily-briefing-design.md:19`); **no Jinja2** (hand-built f-strings). `BriefingType` exists
but does **not** change content. **No scheduler invokes it.**

**⚠ Security** — feed-controlled `finding.title/summary/url` and `task.title` are interpolated into
HTML/markdown **without escaping** (`briefing.py:509-554`) — untrusted RSS content reaches
email/Discord verbatim (injection risk).

**Dead code** — `BriefingService._deliver_discord` (`:372-399`) has no callers; the real chunking is
in `communication_outbox._deliver_discord_chunks`.

---

## F. Summary Engine  (`nexus/intelligence/summary.py`) — the only live intelligence component

`generate_task_summary(task_id)` builds a prompt from the task + latest execution logs/result and
calls OpenRouter (`summary.py:32-92`). **This is the only intelligence component wired into the live
event flow** — invoked by `orchestrator.on_execution_finished` and posted to Discord `#summaries`
(`orchestrator.py:298-311`). Failures are caught and logged without breaking finalization.

**Architecture compliance** — The intelligence layer **respects the "no execution / no
orchestration-state mutation" constraint**: research/briefing write only their own
findings/briefings/outbox rows; summary is read-only; none touch tasks/approvals/executions or spawn
processes (verified). Compliant with `docs/01_ARCHITECTURE.md:398-405`.

---

## Integration gap analysis

**Excellent** — Email failure semantics correctly drive outbox retry; the research/briefing
checkpoint+resume design is thorough; the intelligence layer is cleanly read-only toward
orchestration; Summary is well-integrated.

**Missing** — Scheduler triggers for research/briefing; `RESEARCH_COMPLETED` subscriber;
`EmailProvider` protocol (ADR-007); `DiscordAuthGuard` + unauthorized-attempt auditing (ADR-008);
email templates; circuit breaker/per-model timeout on OpenRouter; tests for Discord/Email/OpenRouter/
Summary.

**Risky** — HTML/markdown injection from untrusted feeds; OpenRouter total-timeout starves
fallbacks; no `max_tokens`; divergent model config sources; business logic + DB access inside the
Discord adapter; channel-fallback misrouting; silent Discord message loss (see `07`).

**Never change** — Intelligence layer's read-only posture toward orchestration; email re-raise →
outbox retry; transactional outbox writes; content-hash briefing dedup + URL/title finding dedup.

**Monitor** — `openrouter_latency_ms` + fallback-exhaustion rate; `llm_summarization_failed_using_fallback`;
feed fetch/parse errors; outbox dead-letters; `briefing_generation_duration_ms`.

**Improve** — see `12`: wire a scheduler + research→briefing chain; escape feed content; per-model
timeout + backoff + `max_tokens`; implement ADR-007/008 abstractions; reconcile model config;
de-triplicate research persist logic; add integration tests.
