# AP-301 Gemini CLI Runtime Adapter Implementation Report

This report outlines the architecture decisions, friction points, and findings discovered during the implementation and validation of the Gemini CLI Runtime Adapter (AP-301).

---

## 1. Architecture Decisions

During implementation, we introduced three structural layers to decouple execution from orchestrator logic:

* **Adapter Contract Boundary**: Defined [BaseRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/base.py#L7-L45), forcing all runtimes to implement standard hooks.
* **Governance Manager**: Created [GovernanceManager](file:///D:/nexus/nexus/execution/governance.py#L18-L125) to validate branch whitelist wildcards, path containment constraints, and command security filters prior to spawning subprocesses.
* **Dynamic Connection Wrappers**: Reused connection sharing wrappers (`SafeSessionWrapper` in test frameworks and validation scripts) to eliminate SQLite transaction concurrency lock conflicts under async executions.

---

## 2. Friction Points & Solutions

* **SQLite Concurrency Contention**: SQLite limits parallel transaction writers, causing locks when asynchronous event handlers write to database tables simultaneously.
  - *Solution*: Orchestrated database writes to execute via shared session wrappers, committing the root transaction only at the exit of logical execution blocks.
* **MagicMock Database Bindings**: In tests, configurations are frequently mocked using `MagicMock()`. Python's `getattr()` dynamically creates a mock for any missing attribute, resulting in string parameter bindings failing inside SQLite.
  - *Solution*: Implemented strict type guards inside [GeminiRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/gemini.py#L18-L290) to check timeouts using `isinstance(t_val, (int, float))` checks before database inserts.
* **Windows Locale File Encoding**: Reading stdout of subprocesses or diffs using default python decoders triggers `UnicodeDecodeError` on Windows systems if git outputs include non-ASCII characters.
  - *Solution*: Intercepted git diff output streams as raw bytes, decoding them manually via `decode("utf-8", errors="replace")`.

---

## 3. Runtime Limitations & Improvements

* **Interactive Prompts**: Subprocess stdout captures can hang if external CLI binaries prompt for operator input. 
  - *Recommendation*: Integrate pseudo-terminal (PTY) emulation inside adapters in later milestones to automate prompt recognition.
* **Connection Pooling**: Migrate to database engines with pooling support (e.g. PostgreSQL) in subsequent phases to support true multi-threaded parallel executions.
