# Phase 2 Action Points: Productization & Core Integrations

Each Action Point (AP) in Phase 2 delivers a distinct, observable piece of user-visible value.

---

## Action Points

### AP-201: Discord Adapter & Interface Setup
* **Title**: Discord Bot and Slash Commands Setup
* **Implementation Scope**: Create Discord client using `discord.py` run in an async task within FastAPI's lifespan. Initialize commands `/task create [title] [description] [priority]` and `/task list`.
* **Visible User Value**: Operators can interact with Nexus directly from their chat application, eliminating the need for terminal DB queries or curl scripts to manage task ingestion.

### AP-202: Interactive Approval Cards
* **Title**: Interactive Governance Gates in Discord
* **Implementation Scope**: Publish task approval requests to `#approvals` as embeds with "Approve" and "Reject" buttons. Verify user ID against configured `owner_ids`. Update embed text dynamically on decision.
* **Visible User Value**: Human operators can securely sign off on tasks using a simple GUI click, automatically progressing blocked tasks to execution.

### AP-203: System Event Outbox Publisher
* **Title**: Resilient Transactional Outbox Daemon
* **Implementation Scope**: Build an asyncio loop daemon polling `system_events` for `pending` events. Route events to their respective Discord channels and mark them as `sent`. Support retry with backoff.
* **Visible User Value**: Real-time operational transparency; state changes (e.g. task completed) are immediately notified to Discord without losing events during network outages.

### AP-204: Execution Notification Hub
* **Title**: Live Terminal Log Streaming to Discord
* **Implementation Scope**: Connect `ExecutionService` and its runner tasks to emit shell commands and step progress. Outbox daemon posts them to the `#execution-log` channel.
* **Visible User Value**: Absolute observability; developers see command execution paths, exits, and output live in Discord.

### AP-205: Summarizer & OpenRouter Integration
* **Title**: Automated Summaries via OpenRouter
* **Implementation Scope**: Implement `OpenRouterClient` via `httpx`. Build prompt assembler to extract `ContextFrame` records, request execution summaries, and write to `#summaries` channel.
* **Visible User Value**: Operators receive clear, high-level summaries of complex command sequences without reading massive log outputs manually.

### AP-206: End-to-End MVP Demonstration & Restart Recovery
* **Title**: Crash-Safe E2E Workflow Proof
* **Implementation Scope**: Establish automated test scenarios simulating process death mid-run. Prove that on restart, the task, approval, and execution engine sweeps recover unfinished items.
* **Visible User Value**: Operators can trust that a server crash will never cause silent failures, duplicate approvals, or lost task executions.
