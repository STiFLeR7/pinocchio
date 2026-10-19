# Phase 3 Action Points

Every action point (AP) in Nexus must answer: *"What visible user value does this create?"*

---

## AP-301: Gemini CLI Runtime Adapter
* **Goal**: Implement a production-grade execution adapter wrapper around Gemini CLI inputs and APIs.
* **Visible User Value**: Enables operators to execute complex engineering tasks (e.g., refactoring code, updating configurations) via Gemini's large context windows.
* **Responsibilities**:
  - Subprocess execution of Gemini commands.
  - Heartbeat logging to prevent task timeouts.
  - Exit code and error capture.
* **Contract Symbols**: [GeminiRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/gemini.py).

---

## AP-302: Claude Code Runtime Adapter
* **Goal**: Implement an execution adapter wrapping the `claude-code` Node CLI binary.
* **Visible User Value**: Enables operations to delegate codebase modifications and commands to Claude Code, providing access to its high-quality coding capabilities.
* **Responsibilities**:
  - Execution of `claude` subprocess pipelines.
  - Capturing standard outputs and ANSI-formatted escape sequences.
  - Adapting outputs to match standard formats.
* **Contract Symbols**: [ClaudeCodeRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/claude.py).

---

## AP-303: Nexus Agent Runtime Evaluation & Adapter
* **Goal**: Investigate and implement Nexus as an execution, planning, and research worker runtime.
* **Visible User Value**: Enables autonomous multi-step planning and file research without operator intervention, reducing manual task detailing.
* **Responsibilities**:
  - Conduct runtime, tool-usage, and planning evaluation.
  - Create [ADR-nexus-runtime-evaluation.md](file:///D:/nexus/blueprint/DECISIONS/ADR-nexus-runtime-evaluation.md).
  - Implement [NexusRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/nexus.py).

---

## AP-304: Repository Governance Layer
* **Goal**: Build an allowed repository directory registry and check runner operations before execution.
* **Visible User Value**: Protects the local server from destructive shell scripts and unauthorized modifications, ensuring secure multi-repository control.
* **Responsibilities**:
  - Implement registry lookup and path validations.
  - Prevent subprocess executions outside target directory boundaries.
  - Enforce branch and command write restrictions.
* **Contract Symbols**: [GovernanceManager](file:///D:/nexus/nexus/execution/governance.py).

---

## AP-305: Execution Artifact System
* **Goal**: Persist and index code patches, git diffs, and generated files as formal database entities.
* **Visible User Value**: Permits operators to audit exact code diffs and download generated outputs directly from Discord or operational reports.
* **Responsibilities**:
  - Capture file modifications made during task executions.
  - Store git diff records.
  - Index patches and outputs in SQLite.
* **Contract Symbols**: [ArtifactRecord](file:///D:/nexus/nexus/memory/models.py).

---

## AP-306: Research Job Engine
* **Goal**: Create scheduled background workflows querying open APIs for framework, model, and library news.
* **Visible User Value**: Delivers up-to-date reports on new model releases and ecosystem updates automatically.
* **Responsibilities**:
  - Schedule background research loops using APScheduler.
  - Perform web searches and summarize findings.
  - Store results in SQLite memory records.
* **Contract Symbols**: [ResearchEngine](file:///D:/nexus/nexus/intelligence/research.py).

---

## AP-307: Daily Briefing Engine
* **Goal**: Generate and distribute operational briefs detailing open tasks, failures, and system status logs.
* **Visible User Value**: Keeps engineering teams aligned on tasks, pending approval gates, and critical failures via daily summaries on Discord and email.
* **Responsibilities**:
  - Compile summaries using Jinja2 formatting templates.
  - Route briefings through Discord webhooks and SMTP email.
* **Contract Symbols**: [DailyBriefingEngine](file:///D:/nexus/nexus/intelligence/briefing.py).
