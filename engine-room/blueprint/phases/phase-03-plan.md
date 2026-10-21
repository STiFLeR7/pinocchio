# Phase 3 Execution Plan — Operational AI Runtimes

This plan outlines the milestones, goals, and architectural objectives for Phase 3. The primary focus of Phase 3 is transforming Nexus from a workflow coordinator into an active operational system by integrating production-grade AI runtime execution adapters, repository governance controls, and autonomous background jobs.

---

## 1. Milestones & Objectives

```
Milestone 3.1: Runtime Adapters & Common Contract (AP-301, AP-302, AP-303)
      ↓
Milestone 3.2: Repository Governance & Security Guardrails (AP-304)
      ↓
Milestone 3.3: Execution Artifacts & Memory Capture (AP-305)
      ↓
Milestone 3.4: Autonomous Background Runtimes (AP-306, AP-307)
```

### Milestone 3.1: Common Runtime Execution Interface
Establish a standard runtime contract and implement execution adapters for Gemini CLI and Claude Code. Evaluate and integrate the Nexus agent framework as a first-class planning and research worker runtime.

### Milestone 3.2: Repository Governance
Implement strict guardrails to prevent AI runtimes from performing unsafe shell commands, accessing directories outside allowed repository paths, or writing directly to restricted branches.

### Milestone 3.3: Execution Artifact Capture
Create a first-class artifact subsystem to capture and index stdout/stderr streams, git diffs, patches, and generated files, ensuring all runtime modifications are persisted in [models.py](file:///D:/nexus/nexus/memory/models.py).

### Milestone 3.4: Autonomous Engine Jobs
Configure background engines for executing scheduled research jobs (AI news, paper summaries) and distributing formatted daily briefings via Discord and email integrations.

---

## 2. System Architecture Layout

Phase 3 introduces the runtime manager subsystem within the `execution/` boundary:

```
                  +--------------------------------+
                  |      WorkflowOrchestrator      |
                  +---------------+----------------+
                                  |
                                  | Dispatches task execution
                                  v
                  +---------------+----------------+
                  |         RuntimeManager         |
                  +---------------+----------------+
                                  |
            +---------------------+---------------------+
            |                     |                     |
            v                     v                     v
+-----------+-----------+ +-------+-------+ +-----------+-----------+
|   Gemini CLI Adapter  | |  Claude Code  | |   Nexus Agent Adapter|
|  (Gemini Run Subproc) | | (Node Subproc)| | (Custom API loop) |
+-----------------------+ +---------------+ +-----------------------+
```

---

## 3. Product Acceptance Criteria

Phase 3 will be considered complete and validated once the following operational flows are demonstrated end-to-end:

1. **Triggered Execution**: A Discord slash command triggers task execution through the orchestrator.
2. **Runtime Governance**: The governance manager validates repository directory limits and branch permissions, raising exceptions if runtimes attempt out-of-bounds operations.
3. **Subprocess Execution**: The Gemini/Claude CLI runtimes execute commands, capturing standard streams and updating database records.
4. **Artifact Persistence**: Generated files, git diffs, and patches are saved in [models.py](file:///D:/nexus/nexus/memory/models.py).
5. **Briefing Delivery**: Daily briefing messages are compiled and sent to both Discord channels and email endpoints.
6. **Research Execution**: Scheduled research jobs run unattended, populating knowledge records.
