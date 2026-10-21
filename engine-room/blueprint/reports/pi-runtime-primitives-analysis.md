# Pi Framework — Pi Runtime Primitives Analysis Report

Date: 2026-06-19
Status: Completed
Author: Antigravity Coding Assistant

---

## 1. Executive Summary

This report performs a deep, meta-level systems analysis of the **Pi Core Runtime Primitives** and the **Agent Loop**. Rather than investigating Pi as a library dependency, we study it as a **runtime architecture reference**. By decomposing the system into its irreducible data building blocks and mapping its state transitions and execution loops, we extract the structural primitives necessary to define the **Nexus Runtime Architecture**.

---

## 2. Runtime Primitive Extraction & Primitive Map

Pi Core's reliability is rooted in a clear separation between **first-class primitives** (durable, serialized inputs/logs) and **derived primitives** (dynamic, reconstructed memory states).

### The Primitive Map

```
+--------------------------------------------------------------------------+
|                            FIRST-CLASS PRIMITIVES                        |
|                                                                          |
|  +--------------------------------------------------------------------+  |
|  | SessionHeader: { id, version, timestamp, parentSession }           |  |
|  +--------------------------------------------------------------------+  |
|                           |                                              |
|                           v                                              |
|  +--------------------------------------------------------------------+  |
|  | SessionTreeEntry Base: { id, parentId, timestamp, type }           |  |
|  +--------------------------------------------------------------------+  |
|        |                  |                   |                  |       |
|        v                  v                   v                  v       |
|  +-----------+     +-------------+     +-------------+     +----------+  |
|  |  Message  |     | StateChange |     | Checkpoint  |     |   Leaf   |  |
|  | (MsgEntry)|     | (ConfigChg) |     | (CompactEntry)    |  (Cursor)|  |
|  +-----------+     +-------------+     +-------------+     +----------+  |
+--------------------------------------------------------------------------+
                               |
                               | (Replay & Reduction)
                               v
+--------------------------------------------------------------------------+
|                             DERIVED PRIMITIVES                           |
|                                                                          |
|  +--------------------------------------------------------------------+  |
|  | SessionContext: { messages[], thinkingLevel, model, activeTools[] } |  |
|  +--------------------------------------------------------------------+  |
+--------------------------------------------------------------------------+
```

### Irreducible Building Blocks

1. **First-Class (Durable) Primitives**:
   - **Entry (`SessionTreeEntry`)**: The atomic building block of all state. Every entry is immutable, has a unique `id`, a reference to a `parentId` (to construct tree structures), and a `timestamp`.
   - **Message (`MessageEntry` / `CustomMessageEntry`)**: Holds actual conversation text, image data, tool calls (`AgentToolCall`), or tool outcomes (`ToolResultMessage`).
   - **StateChange (`ModelChangeEntry` / `ThinkingLevelChangeEntry` / `ActiveToolsChangeEntry`)**: Immutable declarations recording changes in agent configuration.
   - **Checkpoint (`CompactionEntry` / `BranchSummaryEntry`)**: Persisted summarizations of past branches.
   - **Leaf (`LeafEntry`)**: A special cursor pointer that commits the active session tree node.
2. **Derived (Ephemeral) Primitives**:
   - **SessionContext**: The resolved, flattened runtime state containing the active prompt history, model settings, and tools list. It is reconstructed dynamically by starting from a `leaf` and traversing parent IDs up to the root.

---

## 3. Agent Loop Dissection: Think-Act-Observe Phase Model

Most agent systems use a naive `Think -> Act -> Observe` flat loop. Pi Core executes a much richer, transactionally secure phase loop.

```mermaid
stateDiagram-v2
    [*] --> Idle : open session / restore
    
    Idle --> TurnStarted : prompt() / continue()
    note right of TurnStarted: Persistence: Append TurnStarted Event
    
    TurnStarted --> ProviderStreaming : streamAssistantResponse()
    note right of ProviderStreaming: Delta: Emit message_update
    
    ProviderStreaming --> MessageEnded : completion / stopReason
    note right of MessageEnded: Persistence: Append MessageEntry
    
    MessageEnded --> ToolPreflight : extract toolCalls
    note right of ToolPreflight: Hook: beforeToolCall() (Validation & Block)
    
    ToolPreflight --> ToolExecuting : concurrency check (parallel/seq)
    note right of ToolExecuting: Hook: execute() (streams updates)
    
    ToolExecuting --> ToolFinalizing : completion / error capture
    note right of ToolFinalizing: Hook: afterToolCall() (Overwrites)
    
    ToolFinalizing --> MessageEnded : loop tools (if batch not done)
    
    ToolFinalizing --> TurnEnded : all tool results resolved
    note right of TurnEnded: Persistence: Flush pending writes & Save Point
    
    TurnEnded --> Idle : shouldStopAfterTurn == True
    
    TurnEnded --> TurnStarted : getSteeringMessages() / getFollowUpMessages()
```

### Operational Milestones in the Loop

1. **The Interruption Boundary**:
   - Steering messages can only be injected at the **end of a complete turn** (after all tool calls in that turn have completed). The harness prevents user prompts from interrupting mid-execution unless an explicit `abort()` signal is received.
2. **The Queue Drain Point**:
   - Queues are drained in a transaction-like pattern: if a hook fails during queue drainage, the messages are pushed back to the head of the queue (`queue.unshift`) to prevent state loss.
3. **The Save Point Checkpoint**:
   - A `save_point` is not a simple in-memory flag. It is a transaction marker committed only after all message end events have been written, ensuring state persistence before proceeding to callbacks.

---

## 4. Harness Architecture & Operational Discipline

The `AgentHarness` is the critical transaction coordinator that insulates the core execution loop from external runtime changes.

### Harness Responsibilities vs. Exclusions

| Responsibility | Excluded |
|---|---|
| Draining and validating incoming prompt queues. | Concrete tool implementations (only serializable name lists are tracked). |
| Writing state change entries (`pendingSessionWrites`) immediately. | Model provider credentials and network sockets (managed by temporary wrappers). |
| Constructing clean contexts via event reduction. | Hardcoded key check bindings (must be configured dynamically). |
| Isolating tool failures and mapping them to `isError` schemas. | Directly executing un-sandboxed shell code (delegates to an `ExecutionEnv` abstraction). |

### Preventing Chaos
- **Immutable Branching**: When the harness navigates the session tree, it writes a `branch_summary` entry rather than overwriting historical files. This creates a clean rollback trail, ensuring that conversation history is never deleted or corrupted.
- **Pending Write Buffer**: Harness buffers all session mutations during active runs into a `pendingSessionWrites` queue. These are flushed to storage at distinct sync points (on `message_end`, `turn_end`, or `agent_end`), guaranteeing transaction-like write order.
