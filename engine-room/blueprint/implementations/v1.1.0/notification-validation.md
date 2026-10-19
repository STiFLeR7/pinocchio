# Notification Validation

> v1.1.0 bring-up · real outbound delivery.

## Email (SMTP) — ✅ DELIVERED
- Transport: `smtp.gmail.com:587`, STARTTLS, auth via aligned `NOTIFY_*` creds.
- Recipient: `hillaniljppatel@gmail.com`. Subject: "Welcome to Nexus" (text + HTML).
- Log: `connecting_to_smtp_server` → `email_sent_successfully`. Latency ~8.8 s (incl. handshake).
- **Root-caused + fixed blocker:** `EmailService` double-negotiated STARTTLS on :587
  (`connect()` auto-STARTTLS **and** explicit `starttls()`) → `Connection already using TLS`.
  Fix (approved, one line): `aiosmtplib.SMTP(use_tls=False, start_tls=False, …)`.
- Briefing pipeline also dispatched email via the same transport (`report.generated: 2`).

## Discord — ✅ DELIVERED
- Bot **Dex#9955** connected to guild **"STiFLeR's server"** (`guild_id 1464096831779766283`);
  slash commands synced (`discord_slash_commands_synced`).
- `DiscordService.post_message("summaries", embed=…)` resolved a channel and delivered the
  "Welcome to Nexus" embed to **#general** — `message_id 1519643857816649821`
  (`discord_message_posted`).
- **Prior blocker (resolved):** the original `DISCORD_BOT_TOKEN` was invalid
  (`LoginFailure: Improper token`); the operator supplied a valid token. A harness race
  (`wait_until_ready()` called before `start()` initialised) was fixed with a readiness poll.
- Note: the deployed `.env` `DISCORD_*_CHANNEL` keys are still not read by config; channel routing
  currently relies on `settings.discord.channels` resolution (which delivered to #general). Mapping
  those ids is a future polish item, not a blocker.

## Verdict
Email notifications: **Pilot Ready** (real SMTP delivery). Discord notifications: **Pilot Ready**
(real gateway delivery, message id confirmed).
