# COMMUNICATION.md

# Nexus Communication Subsystem

Version: 1.2.0 · Companion to `ARCHITECTURE_CONTINUE.md`, `HARNESS.md`, `ORCHESTRATION.md`

Everything that flows between Nexus and the operator: the channel harness, the
Discord adapter, the transactional outbox, email delivery, and the intelligence
producers that originate proactive messages.

Two delivery paths:

- **Synchronous** — chat replies, posted inline by the Discord adapter as the
  chat pipeline returns a `ChatResponse`.
- **Asynchronous** — notifications, briefings, and the priority feed, written to
  the `system_outbox` table and drained by a background loop (at-least-once,
  retrying, dead-lettering).

---

## 1. Channel harness (`nexus/communication/channels.py`)

Roles, not platforms. Full contract and extension instructions live in
`HARNESS.md` §A; the binding summary:

| Role | Policy | Default Discord channel |
|---|---|---|
| CHAT | replies without mention | `general` |
| NOTIFICATION | post-only, mentions owner | `reminders` |
| PRIORITY_FEED | post-only, mentions owner | `priority_feed` (`priority-feed`) |
| BRIEFING | post-only | `summaries` (`nexus-reports`) |
| APPROVAL | post-only | `approvals` (`nexus-approvals`) |
| SYSTEM | post-only | `console` |

`ChannelRouter` resolves `role → channel_key → concrete channel` outbound, and
`channel name → role` inbound. Producers and the outbox reference only
`channel_key`, never a Discord channel directly.

---

## 2. Discord adapter (`nexus/communication/discord/`)

```
 NexusBot (bot.py)                          DiscordService (service.py)
   intents: message_content, guilds           post_message(channel_key, content, embed, view)
   ChannelRouter(settings.discord.channels)    send_approval_request(...)  → APPROVAL channel
   slash: /task_create /task_list /task_status
   on_message ─▶ ChannelMessage ─▶ ChatService.handle ─▶ _render(ChatResponse)
   ApprovalView: Approve/Reject buttons → verify owner → ApprovalService.evaluate_approval
```

- **Inbound** (`on_message`): normalizes `discord.Message` → `ChannelMessage`
  (`is_owner`, `is_dm` in metadata), responds only on DM, @mention, or a channel
  whose role allows `respond_without_mention` (i.e. `#general`).
- **Outbound** (`_render`): for each `OutboundPost`, resolves
  `router.channel_key(post.role)` and posts (chunked if long); approval cards are
  rendered as embeds with interactive buttons (`ApprovalView`).
- **Slash commands**: `/task_create` (→ create task, transition QUEUED),
  `/task_list` (latest 10 active), `/task_status` (by UUID).

---

## 3. Transactional outbox (`nexus/gateway/communication_outbox.py`)

The reliability backbone for asynchronous delivery. Producers never call Discord
or SMTP directly — they **insert a row**; a loop delivers it.

### 3.1 `system_outbox` record (`nexus/memory/models.py`)

```
 channel        "discord" | "email"
 payload        discord: {content, channel_key}
                email:   {subject, markdown_body, html_body}
 status         pending → processing → sent | retrying | dead_letter
 attempt_count  int (max_attempts = 5)
 correlation_id UUID   (groups a briefing's discord+email rows)
 source_type    "briefing" | "priority_feed"      source_id  → originating record
 next_retry_at  backoff schedule   worker_id  lease holder   last_error / delivered_at
```

### 3.2 Enqueue → lease → deliver → retry

```
 PRODUCER                         DRAIN LOOP (every 2.0s)              DELIVERY
 insert SystemOutboxRecord  ─▶  lease_outbox_items(worker, limit=10)
   status=pending                  pending/retrying & next_retry_at≤now
                                   → status=processing, worker_id, 5-min lease
                                       │
                                       ▼  process_outbox_item
                                   channel=discord → _deliver_discord_chunks(key, content)
                                   channel=email   → EmailService.send_briefing_email(...)
                                       │
                          success ─────┼──── failure
                       status=sent     │   attempt_count++
                       delivered_at    │   < 5 → retrying, next_retry_at = 10*2^n + jitter
                       emit            │   ≥ 5 → dead_letter, emit NOTIFICATION_FAILED
                       NOTIFICATION_SENT
                       update source briefing → "sent" when all sibling rows done
```

- **Chunking** (`_deliver_discord_chunks`): splits on blank/newlines to stay under
  the ~1900-char Discord limit; posts each chunk via `DiscordService.post_message`.
- **Synchronous flush** (`flush_outbox_synchronously`): one-shot delivery of all
  rows for a `correlation_id` — used by briefing in sync/test mode.
- A second, **event-driven** publisher (`nexus/gateway/outbox.py:publish_outbox_loop`,
  also 2.0s) translates domain events (`TASK_*`, `APPROVAL_*`, `EXECUTION_*`) into
  Discord posts on the tasks/alerts/execution_log/approvals channels.

---

## 4. Email delivery (`nexus/communication/email/service.py`)

```
 EmailService.send_briefing_email(subject, text_content, html_content)
   MIMEMultipart("alternative") : text/plain + text/html
   port 465 → implicit TLS ;  port 587 → connect then STARTTLS
   login(username, password) if both present  ;  send_message ; quit
   logs email_sent_successfully | email_delivery_failed   (no secrets logged)
```

SMTP settings come from `EmailConfig` (`.env` `NOTIFY_*` keys mapped in
`config.py`): `smtp_host`, `smtp_port`, `username`, `password`, `from_address`,
`to_address`, `use_tls`. The **email design system**
(`nexus/communication/email/templates/`) renders the HTML body; it is a reusable
asset set (see that directory's `EMAIL_DESIGN_SYSTEM.md` / `DESIGN_DECISIONS.md`).

---

## 5. Intelligence producers (`nexus/intelligence/`)

The originators of proactive communication.

### 5.1 Research engine — `ResearchService` (Job J1, every 2h)

```
 execute_research_run(feeds):
   RSSProvider.collect    (RSS 2.0 + Atom over httpx)
   _deduplicate_findings  (by URL/title vs DB)
   _summarize_finding     (OpenRouter → {summary <100w, importance_score 1–5, tags})
   persist ResearchFindingRecord ; checkpoint each phase
   ─▶ if priority_feed_enabled: PriorityFeedService.dispatch_new_findings(ids)
```

### 5.2 Priority feed — `PriorityFeedService` (`feed.py`)

```
 dispatch_new_findings(finding_ids):
   filter importance_score ≥ priority_feed_min_score (default 4)
   _render_digest  → "🚨 Priority Feed — N high-signal drops"  + @owner mention
                     top priority_feed_max_items (default 5), "+N more" remainder
   enqueue SystemOutboxRecord(channel="discord",
           payload={content, channel_key = router.channel_key(PRIORITY_FEED)},
           source_type="priority_feed")
```

Stays Discord-agnostic: it routes via the channel harness + outbox, never importing
Discord. Dedup is structural — each finding is persisted once per run and only that
run's IDs are dispatched.

### 5.3 Briefing engine — `BriefingService` (Job J2, 08:00 IST)

```
 generate_and_dispatch_briefing():
   aggregate last 24h: findings · open tasks · pending approvals · execution
                       failures · audit (violations/recoveries) · health + metrics
   _render_markdown (Discord)   _render_html (email)
   persist BriefingRecord (content_hash dedup — skip if unchanged)
   enqueue TWO rows (same correlation_id):
     discord: {content: markdown}        source_type="briefing"
     email:   {subject, markdown, html}  source_type="briefing"
```

---

## 6. End-to-end flow (ASCII)

```
 ┌── PRODUCERS ───────────────────────────────────────────────────────────────┐
 │ J1 Research (2h) ─▶ findings ─▶ PriorityFeed (score≥4, @owner)              │
 │ J2 Briefing (08:00) ─▶ aggregate 24h ─▶ markdown + html                     │
 │ Domain events (TASK/APPROVAL/EXECUTION) ─▶ event publisher                   │
 └───────────────┬──────────────────────────────┬───────────────────────────────┘
                 │ enqueue                        │ translate
                 ▼                                ▼
 ┌── system_outbox (transactional) ──┐   ┌── event→discord publisher ──┐
 │ pending→processing→sent           │   │ tasks/alerts/exec/approvals │
 │ lease(10) · retry(2^n) · DLQ      │   │ (2.0s sweep, ≤20)           │
 └───────────────┬───────────────────┘   └──────────────┬──────────────┘
                 │ drain (2.0s)                          │
        ┌────────┴─────────┐                             │
        ▼                  ▼                             ▼
   Discord chunks      Email (SMTP)              Discord channels
   (channel_key →      465 TLS / 587 STARTTLS    (role-bound)
    ChannelRouter)     text + html multipart
        │                                              │
        └──────────────── OPERATOR ◀───────────────────┘
                              │ replies / slash / approval buttons
                              ▼
                   NexusBot.on_message ─▶ ChannelMessage ─▶ ChatService (Dex v2)
```

---

## 7. Reliability properties

- **At-least-once delivery** with idempotent status checks (lease + `worker_id`).
- **Backpressure-aware**: J5 `outbox_health` watches backlog (threshold 100).
- **No secrets in logs**: the email/SMTP path logs outcomes and host/port only.
- **Transport independence**: swap or add a transport by implementing a
  `ChannelMessage`-normalizing adapter + a binding table (`HARNESS.md` §A.6) — the
  outbox, producers, and chat pipeline are unchanged.

See `ORCHESTRATION.md` for cadence/retry numbers in the performance envelope and
`HARNESS.md` for the channel-harness contract these producers route through.
