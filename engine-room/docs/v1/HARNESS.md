# HARNESS.md

# Nexus Harness Guide

Version: 1.2.0 · Companion to `ARCHITECTURE_CONTINUE.md`

Nexus has **two harnesses** — pluggable seams where the system is designed to be
extended without touching the core:

1. **Channel harness** — transport-independent messaging (`nexus/communication/channels.py`).
   Lets new platforms (Slack, Teams, web, email) bind to the same semantic roles.
2. **Runtime harness** — pluggable execution backends (`nexus/execution/runners/`).
   Lets new AI runtimes (CLIs or agent loops) be registered and orchestrated
   identically.

This guide documents both contracts and gives step-by-step instructions to
extend them.

---

## Part A — Channel Harness

### A.1 Why it exists

The core never speaks "Discord". It speaks **roles**. A `ChatResponse` says
"post this card to the SYSTEM role"; the adapter decides that SYSTEM → the
`console` Discord channel. Swap Discord for Slack and the core is unchanged.

### A.2 The contract (`nexus/communication/channels.py`)

```
ChannelRole (enum)            ChannelMessage (inbound, normalized)
  CHAT           "chat"          role            : ChannelRole
  NOTIFICATION   "notification"  author          : str   (platform-agnostic id)
  PRIORITY_FEED  "priority_feed" channel_id      : str
  BRIEFING       "briefing"      conversation_id : str
  APPROVAL       "approval"      message         : str
  SYSTEM         "system"        metadata        : dict  (is_owner, is_dm, …)

ChannelPolicy (per role, _POLICIES)        ChannelRouter
  respond_without_mention : bool             channel_key(role)        -> binding attr name
  post_only               : bool             channel_name(role)       -> concrete channel
  mention_owner           : bool             role_for_channel_name(n) -> inbound role
                                             respond_without_mention(name) -> policy
```

### A.3 Default role policies & bindings

| Role | respond w/o mention | post-only | mention owner | Default Discord channel |
|---|---|---|---|---|
| CHAT | ✅ | — | — | `general` |
| NOTIFICATION | — | ✅ | ✅ | `reminders` |
| PRIORITY_FEED | — | ✅ | ✅ | `priority_feed` (`priority-feed`) |
| BRIEFING | — | ✅ | — | `summaries` (`nexus-reports`) |
| APPROVAL | — | ✅ | — | `approvals` (`nexus-approvals`) |
| SYSTEM | — | ✅ | — | `console` |

`CHAT` is the only role that replies to un-mentioned messages — so `#general` is a
natural conversation, while every other channel is post-only (Nexus speaks when it
has something to say).

### A.4 Inbound & outbound flow

```
 INBOUND   Discord.Message
   └─ NexusBot.on_message
        ├─ role = router.role_for_channel_name(channel.name)
        ├─ build ChannelMessage(role, author, conversation_id, message, metadata{is_owner,is_dm})
        ├─ gate: DM? @mention? or policy.respond_without_mention?  → else ignore
        └─ ChatService.handle(ChannelMessage) ─▶ ChatResponse

 OUTBOUND  ChatResponse.posts = [OutboundPost(role, content|embed)]
   └─ NexusBot._render
        └─ for post: key = router.channel_key(post.role); DiscordService.post_message(key, …)
```

### A.5 HOW-TO — add a new outbound destination (e.g. a "DIGEST" role)

1. Add the role to `ChannelRole` in `channels.py`.
2. Add a `ChannelPolicy` entry in `_POLICIES` (decide `post_only`, `mention_owner`,
   `respond_without_mention`).
3. Add a binding in `_DEFAULT_DISCORD_BINDING` mapping the role → a
   `DiscordChannels` attribute name.
4. Add the channel field to `DiscordChannels` in `nexus/config.py` (with an alias
   if the channel name differs from the attribute).
5. Producers enqueue with `channel_key = router.channel_key(ChannelRole.DIGEST)` —
   no adapter code changes.

### A.6 HOW-TO — add a new transport (e.g. Slack)

1. Write a `SlackBot`/`SlackService` that normalizes inbound events into
   `ChannelMessage` and implements an outbound `post_message(channel_key, …)`.
2. Provide a Slack binding table (role → Slack channel) analogous to
   `_DEFAULT_DISCORD_BINDING`; construct a `ChannelRouter` with it.
3. Reuse `ChatService` unchanged — it consumes/produces transport-neutral types.
4. Wire the new service in `lifespan` next to the Discord wiring.

> The chat pipeline (`Planner→Validator→Executor`) and the outbox never reference
> Discord types — only `ChannelMessage`/`OutboundPost`/`channel_key`.

---

## Part B — Runtime Harness

### B.1 Why it exists

Tasks are executed by interchangeable **runtimes**. Two shapes are supported: a
**CLI runtime** (spawn a subprocess, e.g. Claude Code / Gemini CLI) and an
**agent runtime** (an in-process reasoning/tool loop, e.g. the Nexus agent). The
orchestrator treats them uniformly through a registry + base contract.

### B.2 The registry (`nexus/execution/runners/__init__.py`)

```
runtime_registry : RuntimeRegistry          @runtime_registry.register("nexus")
  register(id, aliases=…)  -> decorator      class NexusRuntimeAdapter(AgentRuntimeAdapter): …
  get_runtime_adapter(id)  -> adapter         (importing the module triggers registration)

 Registered IDs           Adapter                     Kind     Aliases
   "claude"   ClaudeRuntimeAdapter   (CLIRuntimeAdapter)    "claudecode"
   "gemini"   GeminiRuntimeAdapter   (CLIRuntimeAdapter)    —
   "nexus"    NexusRuntimeAdapter    (AgentRuntimeAdapter)  "hermes", "hermesagent"
```

### B.3 The base contract (`nexus/execution/runners/base.py`)

```
BaseRuntimeAdapter (ABC)            lifecycle shared by all runtimes
  initialize()    verify env / API keys (fail-closed)
  heartbeat()     update last_heartbeat (liveness / timeout detection)
  checkpoint(name,state)  persist intermediate state (recovery)
  terminate()     graceful / force kill
  summarize()     -> markdown summary of outputs
  persist()       commit logs + artifacts to DB

CLIRuntimeAdapter (ABC : Base)       AgentRuntimeAdapter (ABC : Base)
  validate(repo, cmd)                  validate_goal(goal)
  execute(cmd) -> dict (metrics)       execute_goal(goal) -> dict (status, …)
```

The orchestrator dispatches on kind:

```
adapter = get_runtime_adapter(task.runtime_id)
adapter.initialize()
if isinstance(adapter, CLIRuntimeAdapter):  adapter.validate(repo,cmd); r = adapter.execute(cmd)
else:                                        adapter.validate_goal(cmd);  r = adapter.execute_goal(cmd)
adapter.checkpoint(...); adapter.persist()
ExecutionService.finalize_execution(execution_id, resolve_exit_status(r), r)
```

### B.4 Timeouts, budgets & terminal status (enforced)

| Runtime | Timeout field (`ExecutionConfig`) | Default | Ceiling |
|---|---|---|---|
| Nexus agent (research) | `research_timeout` | 900s (15m) | `hard_limit` |
| Gemini CLI | `gemini_timeout` | 1800s (30m) | `hard_limit` |
| Claude CLI | `claude_timeout` | 2700s (45m) | `hard_limit` |
| Absolute ceiling (A-002) | `hard_limit` | 3600s (60m) | — |
| Agent step budget (H-4) | `agent_max_steps` | 5 | — |

`resolve_execution_timeout(settings, field)` clamps any runtime to `hard_limit`.
Agent runtimes report **truthful terminal status** —
`completed | failed | timed_out | cancelled` — which `resolve_exit_status()`
maps to `SUCCESS | FAILURE | TIMEOUT | CANCELLED` (CLI runtimes fall back to
exit-code mapping). Agents also honour **cooperative cancellation** (a
`_cancel_requested` flag or DB-observable `exit_status == CANCELLED`) and can
`resume_goal()` by replaying `agent_steps` from the last checkpoint.

### B.5 HOW-TO — add a new runtime

1. Create `nexus/execution/runners/<name>.py`.
2. Subclass `CLIRuntimeAdapter` (subprocess) or `AgentRuntimeAdapter` (reasoning
   loop). Implement the abstract methods; call `resolve_execution_timeout(...)`
   for any wait, and run commands through `SandboxManager` (never raw subprocess).
3. Decorate the class: `@runtime_registry.register("<name>", aliases=[...])`.
4. Ensure the module is imported so the decorator runs (the registry's
   `get_runtime_adapter` imports known modules; add yours there).
5. Route work to it by creating a task with `runtime_id="<name>"`
   (`runtime_type="cli"|"agent"`). No orchestrator changes are required.

### B.6 Governance & sandbox (always on the path)

Every runtime validates **before** doing work:

- CLI: `GovernanceManager.validate_execution(task_id, working_dir, command, runtime)`
  checks the repository whitelist and command policy.
- Agent: file tools are confined to the workspace (`resolve_in_workspace()`, R-05);
  commands run via `SandboxManager` under the configured network/filesystem policy.

See `ORCHESTRATION.md` for how the harness sits inside the task → approval →
execution pipeline, and `05_CRITICAL_CONSTRAINTS.md` for the governance invariants.
