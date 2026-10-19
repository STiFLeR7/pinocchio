# Discord Integration Architecture & Design

This document details the interface adapter design for integrating Discord as the primary operational UI for Nexus.

---

## 1. Architectural Role: Decoupled Interface Adapter

Discord functions exclusively as a **read/write interface adapter**. 
* **State Constraint**: No state is stored within the Discord bot or channels. Discord is entirely stateless from the perspective of the Nexus Control Plane. 
* **Single Source of Truth**: All states, settings, and relationships reside in the relational SQLite database.
* **Resilience**: If the Discord bot disconnects, crashes, or is rate-limited, the local database remains consistent. The event outbox daemon guarantees that notifications are queued and dispatched once the connection is restored.

---

## 2. Component Design & Lifecycle

```
┌────────────────────────────────────────────────────────┐
│                     FastAPI Engine                     │
│                                                        │
│  ┌───────────────────┐        ┌───────────────────┐    │
│  │   Uvicorn Server  │        │  Discord Bot Task │    │
│  │   (API Endpoints) │        │   (discord.py)    │    │
│  └─────────┬─────────┘        └─────────▲─────────┘    │
│            │                            │              │
│            ▼                            ▼              │
└────────────┼────────────────────────────┼──────────────┘
             │                            │
             │     ┌────────────────┐     │
             └────►│ SQLite DB /    │◄────┘
                   │ transactional  │
                   │ outbox         │
                   └────────────────┘
```

### Lifespan Integration
The Discord bot is registered as a background task during the FastAPI startup hook inside `nexus/api.py`. The task runs concurrently with the web server, sharing the database engine.

---

## 3. Channel Mapping Configuration

Settings are parsed from `config/settings.yaml` to route messages to specific channels:
* `#inbox`: Input commands and system startup status.
* `#tasks`: Real-time creation and update confirmations.
* `#approvals`: Human-in-the-loop manual approval embeds with button interfaces.
* `#execution-log`: Streamed stdout/stderr log blocks from runner executions.
* `#summaries`: Compiled executive digests and reports.
* `#alerts`: Error notifications, timeouts, and failure run alerts.

---

## 4. Interaction Handlers

### Slash Commands
* `/task create [title] [description] [priority]`: Initiates task creation. The bot maps parameters to the `TaskCreate` schema and invokes `TaskService.create_task`.
* `/task list`: Lists active and blocked tasks.

### Message Component Buttons (Approvals)
* **Design**: Embeds created in `#approvals` include two buttons:
  * `Approve` (`custom_id="approve_<approval_id>"`, Style: Success/Green)
  * `Reject` (`custom_id="reject_<approval_id>"`, Style: Danger/Red)
* **Auth Check**: Upon button interaction, the bot checks the Discord user ID against the authorized list (`settings.discord.owner_ids`).
* **Processing**: If validated, it calls `ApprovalService.evaluate_approval` and edits the embed to display approval status (e.g. `Approved by Owner [ID] on [timestamp]`). If unauthorized, it raises an ephemeral error.
