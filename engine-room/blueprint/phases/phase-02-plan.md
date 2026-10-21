# Phase 2 Implementation Plan: Control Plane Productization

This document details the plan to turn the verified Nexus Phase 1 infrastructure into a user-visible, operational control plane driven by Discord.

---

## 1. Objective

Deliver a complete user-visible E2E workflow where a human operator can manage the entire task lifecycle—from task creation and manual governance to automated execution, log inspection, and summary generation—directly through Discord, backed by a resilient, crash-recoverable SQLite memory layer.

---

## 2. Key Milestones

### Milestone 1: Discord Bot Interface & Command Routing
* **Goal**: Establish the running bot loop, validate configuration credentials, and support `/task create` and `/task list` commands.
* **User Value**: Users can define and inspect tasks from within their operational workspace.

### Milestone 2: Interactive Approval Cards & Human Governance
* **Goal**: Generate rich embeds on Discord when a task is blocked on approval. Bind interactive buttons that verify the `owner_id` context and trigger the transition to approved state.
* **User Value**: Owners can securely authorize operations with one click, ensuring strict gating.

### Milestone 3: Execution Hub & Subprocess Stream Delivery
* **Goal**: Integrate the execution runner to spawn tasks, capture logs, write them back to DB, and stream them live to a dedicated `#execution-log` channel.
* **User Value**: Full operational transparency; developers see terminal execution commands and stdout/stderr as it runs.

### Milestone 4: Automated Summaries & OpenRouter Integration
* **Goal**: Integrate `httpx` based OpenRouter client to compile context frames and summarize outcomes, publishing logs in `#summaries`.
* **User Value**: Executive visibility; provides digests of task execution and status reports.

### Milestone 5: Recovery Demonstrations
* **Goal**: Build integration scenarios proving that system crashes during any of the above states are fully recovered upon daemon restart.
* **User Value**: Enterprise-grade durability and zero lost states.

---

## 3. Transition Strategy & Safety Guards

* **Memory remains the Source of Truth**: Under no circumstances does Discord hold local state or bypass database writes. If Discord disconnects, the outbox publisher retries delivery.
* **Strict Validation Rules**: All slash inputs are sanitized and parsed into Pydantic models before hitting the `TaskService`.
* **Subprocess Log Clamping**: Subprocess logs are captured in 64KB blocks, with a total limits safeguard of 1MB, preventing database size bloat.
