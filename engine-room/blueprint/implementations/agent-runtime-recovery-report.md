# Agent Runtime Recovery Report

This report outlines the checkpointing, recovery logic, and state consistency verification for autonomous agent runtimes in Nexus.

---

## 1. Heartbeats and Checkpointing

During the tool-calling loop, [NexusRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/nexus.py) writes regular indicator status updates to the database:

* **Liveness Heartbeats**: Before executing any tool, the adapter updates the parent `ExecutionRecord.last_heartbeat` timestamp via the `heartbeat()` method. This prevents the orchestrator thread scheduler from flagging the active runner as timed out.
* **State Checkpoints**: After every reasoning iteration, the adapter calls `checkpoint()`, serializing the active planning steps and trajectory index into the `workflow_checkpoints` SQLite table.

---

## 2. Restart and Crash Recovery Loop

If the Nexus control plane shuts down abruptly mid-run:
1. Active tasks remain in their last registered state (`active`, `blocked`) inside SQLite.
2. Upon restart, the orchestrator triggers a cleanup/recovery routine.
3. The scheduler scans for active executions. If the `last_heartbeat` exceeds the threshold limit, the orchestrator retrieves the latest serial checkpoint from the `workflow_checkpoints` table.
4. The system is able to restore the agent's memory, trajectory, and plan, allowing the task execution to resume from the last completed tool invocation.

---

## 3. Validation Verification

In E2E restart validation scenarios, the engine verifies that:
* Tasks remain safely `blocked` or `active` inside SQLite rather than entering corrupted states.
* Database session handlers successfully reload model records after system boot, confirming transaction safety.
