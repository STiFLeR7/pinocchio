# Pi Framework — Pi Context & Recovery Architecture Report

Date: 2026-06-19
Status: Completed
Author: Antigravity Coding Assistant

---

## 1. Executive Summary

This report performs a deep architectural analysis of the **Context Engineering** and **Crash Recovery** systems within Pi Core. We examine how Pi manages context windows, prevents token expansion decay, and recovers conversation states from process crashes. These systems-design mechanisms are translated into structured recommendations for the **Nexus Memory and Task Engine subsystems**.

---

## 2. Context Engineering: Preventing Context Entropy

In long-running sessions, context entropy (redundant logs, repeating tool results, and excessive token usage) degrades LLM reasoning. Pi Core controls this via an explicit context compiler.

### Context Assembly and Replay
Every time a new LLM call is prepared, the context is assembled from scratch by traversing the log tree from the active `leaf` back to the root parent.

```
(Root)
  |
  +--> [ModelChangeEntry]  -------------> Sets model to "gemini-2.5-pro"
  |
  +--> [ActiveToolsChangeEntry]  -------> Restores toolset ["read", "write"]
  |
  +--> [CompactionEntry (CheckPoint)]  -> Summarizes Dialog up to this point
  |      \__ (Prunes messages before)
  |
  +--> [MessageEntry (User)]  ----------> "Perform search"
  |
  +--> [MessageEntry (ToolResult)]  ----> "Results list" (active prompt start)
  |
(Leaf Cursor)
```

1. **Incremental Configuration Reconstruction**:
   - As the harness traverses entries, it reduces configuration state dynamically. If it encounters a `model_change` or `thinking_level_change` entry, it updates the runtime parameters. This ensures that configuration changes are bound to the conversation branch itself.
2. **The Compaction Barrier**:
   - If a `compaction` entry exists on the path, the context traversal splits.
   - All messages prior to `compaction.firstKeptEntryId` are **pruned** from the active context.
   - The compaction's summarized text is injected as a single synthetic message at the beginning of the context. This bounds the context window size while retaining historical context.

### Coherence Over Long Sessions
By using trees instead of flat lists, the agent can navigate to different branches (`navigateTree`) and reconstruct the exact context that existed on that branch, allowing developers to execute rollback trials without cross-contaminating other branches.

---

## 3. Recovery Architecture: Managing Crashes & Tool Failures

A production orchestrator must recover gracefully from crashes during active tool execution.

### Persistence, Reconstruction, and Replay Boundaries

| Phase | What is Persisted | Reconstructed on Restart | Replay Policy |
|---|---|---|---|
| **API Request** | `TurnStarted` event + in-flight queues. | The state tree up to the last stable leaf node. | Provider request stream is lost; marked as interrupted. The turn is retried. |
| **Tool Execution** | `ToolCallStarted` event with `toolCallId` and arguments. | Active execution context. | If the tool is not declared `retry-safe`, it appends a `ToolCallFinished` entry with `isError: true` and blocks automated execution. |
| **Compaction** | `CompactionEntry` with first kept entry ID. | Truncation boundary is verified. | Re-runs compaction if the entry was not successfully written. |

### Failure Isolation Mechanics
- **Unfinished Tool Runs**: If a crash occurs during a bash or command run, the system must not guess the outcome. Upon database restore, it reads the incomplete `ToolCallStarted` entry and immediately appends an error result to prevent repeating unsafe actions.
- **Durable Queues**: Message queues (steering and follow-up prompts) are written to the session database prior to consumption. A crash does not lose queued user commands; they are recovered during session log reduction.
