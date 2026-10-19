# 13 — First-Week Operator Guide

> Read-only audit output. How to run, configure, and operate Nexus v1.0.0 as a single operator.
> Commands are quoted from the repo docs and verified against code; ⚠ marks known traps this audit
> found. This is a *pilot* runbook, not a production SRE guide.

---

## Day 1 — Mental model & setup

**What you are operating:** a long-lived FastAPI process that you talk to mainly through Discord. It
receives tasks, asks you to approve privileged execution, runs approved commands against
allow-listed repositories, and records everything in a local SQLite database. **You are the
governor** — nothing executes without your Discord approval (`execution/service.py:43-45`).

**Setup (from `DEVELOPMENT.md:26-53`):**
```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows bash; or .venv\Scripts\activate
pip install -e ".[dev]"              # or: uv sync
cp config/settings.example.yaml config/settings.yaml   # then edit
alembic upgrade head                  # ⚠ see trap T-1 below
```
⚠ **Trap T-1:** On a *clean* database `alembic upgrade head` may fail — several tables (incl. the base
`repository_registry`) have no migration, and the app actually builds its schema at boot via
`Base.metadata.create_all` (`api.py:81-83`). If migrations fail, the app will still create the
schema on first start. (`06-database-map.md` has detail.)

⚠ **Trap T-2:** `DEVELOPMENT.md:52` says to verify with `python -m nexus --health-check`. **This flag
does nothing** — `__main__` ignores argv and starts the server (`__main__.py:34-40`). Use the
`/health` HTTP endpoint instead (below).

## Day 2 — Configuration (the most error-prone part)

⚠ **Trap T-3 — two config systems.** There is a flat `.env` (vars like `DISCORD_BOT_TOKEN`,
`OPENROUTER_API_KEY`, `GROQ_API_KEY`, `RESEND_API_KEY`, `DISABLE_SEMANTIC_MEMORY`, `DISCORD_*_CHANNEL`)
**and** a nested `config/settings.yaml` (`discord`, `email`, `openrouter`, `database`, `execution`,
`logging`). They do **not** share keys. The code reads settings via pydantic from
env (`NEXUS_*`, plus explicit `DISCORD_BOT_TOKEN`/`DISCORD_GUILD_ID`/`DISCORD_OWNERS`/
`OPENROUTER_API_KEY`) and `config/settings.yaml` (`config.py:156-192`). The `.env` extras like
Groq/Resend/`DISABLE_SEMANTIC_MEMORY` are **not consumed by the code** — don't assume setting them
changes behavior.

**Must-set before any pilot:**
1. ⚠ **`owner_ids`** (`discord.owner_ids` in YAML, or `DISCORD_OWNERS` comma-separated Discord user
   IDs). **If empty, approval auth is disabled and anyone can approve** (`config.py:42`,
   `approvals/service.py:94`, `bot.py:53`). This is the #1 safety setting.
2. **`discord.token`** + **`discord.guild_id`** + channel IDs (`tasks`, `approvals`, `alerts`,
   `execution_log`, `summaries`). ⚠ If a channel isn't resolvable, the bot falls back to the *first
   text channel* (`bot.py:213-215`) — approvals could post to the wrong place.
3. **`openrouter.api_key`** (for summaries/research).
4. **`config/repositories.yaml`** — the execution allow-list. Only registered, active repos can be
   targets; the governance gate enforces realpath containment (`governance.py:149-175`).

⚠ **Trap T-4 — secrets.** The repo's `.env` contains live-looking credentials
(`.env:1-19`). It is gitignored, but treat those keys as compromised and **rotate them**, and avoid
`docker-compose` baking them into images (`docker-compose.yml:16`).

⚠ **Trap T-5 — sandbox isolation is OFF by default.** `sandbox.enabled=False` → commands run
directly on the host (`config.py:101`). For anything beyond fully trusted commands, enable the
Docker provider (`sandbox.enabled=true`, `provider=docker`) — but note the Docker image lacks the
agent CLI binaries (`ADR-011:17-24`).

## Day 3 — Starting and checking it

**Start (local, recommended for pilot):**
```bash
python -m nexus                 # serves on 0.0.0.0:8000 (hardcoded, __main__.py:34-40)
# or: uvicorn nexus.api:app --host 0.0.0.0 --port 8000
```
**Start (Docker):** `docker-compose build && docker-compose up -d` (`DEVELOPMENT.md:143-152`).
⚠ The container can run the control plane but **cannot perform real agent execution** (no local
binaries / no local repos).

**Health checks:**
- `GET http://localhost:8000/health` → `{status, version, timestamp}`; HTTP **503** if unhealthy
  (`api.py:186-200`). ⚠ This reflects a one-time boot-time `git --version` probe, not live DB/Discord
  health (`health.py:49-71`).
- `GET /api/v1/status` → fuller view, but ⚠ all subsystems report `"stub"` (`api.py:223-228`) — this
  is a known cosmetic bug, not an outage.

## Day 4 — Driving a workflow

1. In Discord, `/task_create` with a title/description. Prefix the description with `cmd:` to run a
   shell command or `goal:` for a Nexus goal (`orchestrator.py:145-152`). ⚠ With no prefix and empty
   description it runs a hardcoded `echo` (`orchestrator.py:145`).
2. The bot posts an **approval card** to `#approvals`. Click **Approve** (only owners can).
3. Execution runs under the governance gate; logs/diff/summary are persisted; a summary posts to
   `#summaries`.
4. `/task_list` and `/task_status <id>` to inspect.

⚠ **Trap T-6 — execution timeouts.** Regardless of configured tiers, every CLI run is currently
capped at **300 seconds** (`runners/claude.py:83` field-name bug). Long jobs will be killed at 5 min.

⚠ **Trap T-7 — autonomy is not running.** There is no scheduler. Daily briefings, scheduled research,
and approval-expiration sweeps **do not fire on their own** (`research.py:218`, `briefing.py:74`,
`approvals/service.py:184` are uncalled). If you expect autonomous digests, they won't arrive.

## Day 5 — Operating continuously & recovering

**Where state lives:** `./data/nexus.db` (SQLite + WAL; `nexus.db-wal`, `nexus.db-shm` alongside).
Backups = copy these three files while the process is stopped or quiesced.

**Logs:** structured JSON to stdout/stderr (no file sink). Capture stdout to a file if you need
history.

**Restart behavior:** State survives restart (event sourcing + checkpoints). The outbox redelivers
undelivered Discord/email messages. ⚠ But there is **no auto-resume of in-flight executions** and no
orphan reaper — a task mid-execution at crash time will not self-resume; check `executions` for rows
with a stale `last_heartbeat`.

**DB locked (`SQLITE_BUSY`):** if the DB is stuck, stop the app and remove WAL sidecars:
`rm data/nexus.db-wal data/nexus.db-shm` (`DEVELOPMENT.md:327-331`).

**Approvals stuck:** because expiration never sweeps, an un-actioned approval leaves its task
`BLOCKED` forever. Decide it in Discord, or update the DB manually.

⚠ **No emergency bypass:** if you lose Discord access, there is no built-in way to approve/abort
(`final-architecture-review.md:24`). Keep DB access as your fallback.

---

## Operator quick reference

| Need | Action | Source |
|---|---|---|
| Start | `python -m nexus` | `__main__.py:34` |
| Health | `GET /health` (503=unhealthy) | `api.py:186` |
| Create task | Discord `/task_create` (use `cmd:`/`goal:`) | `bot.py:225`, `orchestrator.py:145` |
| Approve | Discord Approve button (owner only) | `bot.py:52-98` |
| Data location | `./data/nexus.db` (+WAL) | `config.py:76` |
| Backup | copy `nexus.db*` while quiesced | — |
| DB unlock | stop app, `rm *.db-wal *.db-shm` | `DEVELOPMENT.md:327` |
| Migrations | `alembic upgrade head` (⚠ may fail clean; app create_all covers it) | `DEVELOPMENT.md:235` |

**Top 3 things that will bite a new operator:** (1) forgetting `owner_ids` → no real auth;
(2) expecting autonomous briefings/research that never run; (3) the 5-minute execution cap.
