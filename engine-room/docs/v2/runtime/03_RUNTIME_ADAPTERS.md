# 03 — Runtime Adapters

**Status:** design only. Defines the **Runtime Adapter** as a single *conceptual
contract* — a driver boundary, not a Protocol, class, or API. Every runtime Nexus will
ever support satisfies this one contract, and **all** provider-specific knowledge lives
here and **nowhere** in the Runtime Manager (RM) core.

This document is conceptual. It introduces no interface signature, no method list as
code, no algorithm. It describes responsibilities, the boundary, a mapping of example
runtimes onto the same contract, and the discipline that lets unknown future runtimes
join without redesign. It cross-references its siblings by filename:
`00_RUNTIME_OVERVIEW.md`, `01_RUNTIME_MANAGER.md`, `02_RUNTIME_SESSION.md`,
`04_RUNTIME_REGISTRY.md`, `05_RUNTIME_CAPABILITIES.md`, `07_RUNTIME_LIFECYCLE.md`,
`15_RUNTIME_EVENTS.md`.

---

## 1. What a Runtime Adapter is

A **Runtime Adapter** is the thin, provider-specific boundary that makes one concrete
runtime — Claude Code, Gemini CLI, a shell, a Docker container, a Python process, a
browser driver, an MCP server, a remote worker — look identical to RM's generic core.
It is the *only* place in `nexus_runtime` where the words "Claude", "Docker", "browser",
or "subprocess" may appear.

> An adapter is a **driver**. It translates between RM's runtime-agnostic vocabulary
> (configure, start, stream, progress, artifact, cancel, terminal status, clean up) and
> one provider's concrete mechanics. It is **never a decision-maker.**

A "Runtime" is a Harness of category `RUNTIME` (ADR-002; `00_RUNTIME_OVERVIEW.md` §7).
The adapter is what *fronts* that runtime for RM. The adapter registers a **Runtime
Descriptor** into the Registry view (`04_RUNTIME_REGISTRY.md`), advertising the abstract
capabilities (`05_RUNTIME_CAPABILITIES.md`) the runtime can satisfy. RM reads that view;
the adapter never reaches into RM.

The adapter has a precise place in the platform spine: **RM prepares execution; the
Execution Engine performs it** (`00`, `01`). The adapter is the mechanism through which
the engine *performs* and through which RM *observes* — but the adapter itself decides
nothing about *what* runs or *whether* it succeeded.

## 2. The conceptual contract (responsibilities, not signatures)

Every adapter, regardless of provider, is responsible for exactly the following
concerns. Each is a *responsibility*, expressed in prose — there is no method list here,
by design.

| # | Responsibility | What the adapter must do | What it must NOT do |
|---|---|---|---|
| A | **Advertise capabilities** | Publish a Runtime Descriptor into the Registry view (`04`): identity, version, advertised abstract capabilities (`05`), declared isolation surface, configuration shape | Decide whether *this* package should run here (that is selection, `06`) |
| B | **Configure** | Accept RM's rendered, declarative configuration (env, working dir, resource limits, isolation profile, injected secret references, optional recovery-checkpoint reference) and translate it into provider-specific setup | Invent configuration RM did not supply; read upstream repositories |
| C | **Start** | Bring the runtime to the point where the Execution Engine can drive the Work Package inside it (spawn process, launch container, open browser, connect to MCP/remote endpoint) | Decide *that* it should start, or *what* the work is — it receives a Work Package (INV-09) |
| D | **Stream** | Surface the runtime's stdout/stderr/structured output as runtime-independent stream events for RM to record (`08`, `runtime.output`) | Interpret, grade, or summarize the output |
| E | **Report progress** | Translate whatever progress signal the runtime offers — phases, fractions, milestones, or *unknown* — into RM's progress model (`12`, `runtime.progress`) | Fabricate progress the runtime did not express |
| F | **Emit artifacts** | Surface produced files, logs-as-artifacts, metrics, and structured outputs as **Evidence Candidates**, referenced by id (`13`, `runtime.artifact_emitted`, ADR-003) | Embed artifact content in events; declare an artifact "validated" (that is Validation's, INV-20) |
| G | **Honor cancel / timeout / pause** | Carry out RM's control signals against the provider — graceful then forced cancellation (`09`), timeout-driven stops (`10`), suspend/resume (`07` `Paused`/`Waiting`) | Decide *when* to cancel, time out, or pause — RM/Strategy own that; the adapter executes it |
| H | **Report terminal status** | Report that the runtime **process** ended, and how (normal exit, error, killed), so RM can project `Completed`/`Cancelled`/`Failed` (`07`) | Report "success"; `Completed` means the process ended, not that the work is valid (INV-20) |
| I | **Clean up** | On teardown, release everything provider-specific: kill processes, remove containers, tear down temp workspaces, revoke credential handles, close connections (`07` §6, `17`) | Leak capacity or secrets; suppress a cleanup failure (it is surfaced as a typed teardown error, `11`) |

The contract is **complete and closed**: these nine concerns are the entire surface RM
needs from any runtime. A new provider does not add a tenth concern — it supplies its
own translation for these nine.

## 3. The strict boundary: all provider knowledge lives here

This is the load-bearing rule of the whole subsystem.

```
        ┌──────────────────────── nexus_runtime ────────────────────────┐
        │                                                                │
        │   RM CORE (generic)                 RUNTIME ADAPTERS (specific)│
        │   ─────────────────                 ──────────────────────────│
        │   • preparation pipeline (01)       • Claude adapter          │
        │   • Runtime Session (02)            • Gemini adapter          │
        │   • capability matching (05)        • Shell adapter           │
        │   • selection + allocation (06)     • Docker adapter          │
        │   • lifecycle projection (07)       • Python adapter          │
        │   • streaming/progress/artifact     • Browser adapter         │
        │     models (08/12/13)               • MCP adapter             │
        │   • runtime.* events (15)           • Remote-worker adapter   │
        │                                     • <future> adapter        │
        │   knows: capabilities, sessions,    knows: HOW one provider    │
        │   states, events — NOT providers    starts/streams/cancels     │
        └────────────────────────────────────────────────────────────────┘
                 ▲                                          │
                 │  drives generically                      │ translates to
                 └──────────────────────────────────────────┘  one provider
```

- RM core reasons only in the abstract vocabulary of `00`–`02`, `05`–`07`, `15`. It
  never branches on `if runtime == "claude"`. If such a branch appears in RM core, the
  architecture has been violated.
- Provider-specific code — process spawning, container APIs, browser drivers, MCP
  handshakes, SSH/remote transport, vendor SDKs — lives **only** behind an adapter,
  consistent with `00` §4 ("the only place provider-specific code will ever live is
  inside individual Runtime Adapters").
- The litmus test from `01` §3 applies to adapters too: an adapter may change *where*
  and *how* already-decided work is hosted; it may never change *what* runs or *whether*
  it succeeded. Anything that would change those belongs to Planning, Orchestration,
  Validation, or Recovery — never an adapter.

## 4. The same contract, eight ways

Every example runtime maps onto the **identical** nine-concern contract from §2. The
columns below show provider mechanics; the rows show that the *contract* is constant
while the *mechanics* vary. None of this variation is visible to RM core.

| Runtime | How it starts (C) | How it streams (D) | How it reports progress (E) | How it emits artifacts (F) | How it cancels (G) | Isolation surface (B/I) |
|---|---|---|---|---|---|---|
| **Claude Runtime** | Launch Claude Code agent session fronting the Work Package | Agent turn output / structured events as stream lines | Phase + milestone events from the agent loop (often coarse) | Files & structured outputs referenced as Evidence Candidates | Signal agent to stop; force-kill the session if unheeded | Agent session sandbox, scoped workspace, injected credential refs |
| **Gemini Runtime** | Launch Gemini CLI process for the Work Package | CLI stdout/stderr lines | CLI step markers; often *unknown* fraction | Output files / CLI result payloads referenced | Terminate CLI process; escalate to force | Process sandbox, working dir, env-scoped keys |
| **Shell Runtime** | Spawn a shell command/script | Raw stdout/stderr | Usually *unknown*; milestones only if the script emits them | Files written; captured stdout-as-artifact | SIGTERM then SIGKILL on the process group | OS process boundary, cwd, ulimits |
| **Docker Runtime** | Create + start a container from an image | Container log stream (stdout/stderr) | *Unknown* unless the containerized program reports it | Files in mounted/exported volumes referenced | `stop` (graceful) then `kill` the container | Container namespace — strongest isolation surface here |
| **Python Runtime** | Start a Python process/interpreter for the package | Interpreter stdout/stderr + structured logs | Library-emitted progress if present; else *unknown* | Files, pickled/serialized outputs, metrics referenced | Terminate the interpreter process; force-kill | Process sandbox, venv, resource limits |
| **Browser Runtime** | Launch a browser driver session | DOM/console/automation event stream as lines | Step/navigation milestones; rarely a fraction | Screenshots, DOM captures, downloaded files referenced | Close the driver session; force-kill the browser | Browser profile sandbox, ephemeral profile, network scope |
| **MCP Runtime** | Connect to an MCP server endpoint | MCP notifications/tool-output as stream events | Server-reported progress notifications if offered; else *unknown* | Tool-result payloads / referenced resources as Evidence Candidates | Cancel the in-flight request; disconnect | Server-side boundary; connection + credential scope |
| **Remote-Worker Runtime** | Dispatch the package to a remote worker over a transport | Streamed remote stdout/events relayed back | Worker-reported progress heartbeats; else *unknown* | Remote-produced files/outputs referenced (by id) | Send remote cancel; force-disconnect; reclaim on the worker | Remote host/process boundary; transport + credential scope |

Read the table by row to see one runtime; read it by column to see that the *concern* is
identical everywhere — only the translation differs. That invariance is the entire point
of the adapter boundary. Where a runtime cannot express something (e.g. a true progress
fraction), the adapter reports the honest model value — including **unknown** progress
(`12`) — rather than inventing one (responsibility E).

## 5. Designing for runtimes not yet known

The contract is closed precisely so that the *set of runtimes* can stay open. A runtime
that does not exist today — a new vendor CLI, a WASM sandbox, a GPU job scheduler, a
voice agent, a distributed actor — joins Nexus by supplying an adapter that satisfies the
same nine concerns. Nothing upstream changes.

| Pressure from a new runtime | Where it is absorbed | What does NOT change |
|---|---|---|
| A novel start mechanism | The adapter's translation for concern C | RM's preparation pipeline (`01`), session model (`02`) |
| An exotic stream/progress shape | The adapter mapping for D/E, degrading to *unknown* where needed (`12`) | The streaming/progress models (`08`/`12`) |
| A new artifact kind | The adapter mapping for F → Evidence Candidate by reference (`13`) | The artifact model and `runtime.artifact_emitted` (`15`) |
| A different cancel/isolation surface | The adapter mapping for G/I and the declared isolation surface (`17`) | The lifecycle states (`07`) and `runtime.*` events (`15`) |
| A new capability it can satisfy | A new abstract Capability (provider-independent, INV-32) advertised in its descriptor (`04`/`05`) | The capability *model* and matching rules (`05`) |

Guarantees that make this safe:

- **No provider-specific assumptions in RM core.** Adding a runtime is adding a
  directory of adapter code plus a Registry registration — never an edit to RM core,
  upstream layers, ADRs, or invariants (`19_RUNTIME_EXTENSIBILITY.md`).
- **Capabilities, not providers, are matched.** Because capabilities are
  provider-independent (INV-32, `05`), an unknown runtime that advertises a known
  capability is selectable the moment it registers — no special-casing.
- **Lifecycle and events are fixed.** A new adapter must project onto the canonical
  states (`07`) and emit only the canonical `runtime.*` events (`15`). It may not coin a
  new state or event; it maps its provider reality onto the existing vocabulary.
- **Honest degradation.** Where a runtime cannot express a concern, the adapter reports
  the model's "unknown"/"unsupported" value (`05`, `12`) rather than fabricating — so the
  rest of the system reasons over truthful facts.

## 6. The adapter is a driver, never a decision-maker

This is restated deliberately because it is the easiest boundary to erode.

| The adapter MAY (driver acts) | The adapter MAY NOT (decisions that belong elsewhere) |
|---|---|
| Translate RM's configuration into provider setup (B) | Choose which runtime should host a package — that is selection (`06`, INV-21) |
| Start/stop/suspend the runtime on RM's signal (C/G) | Decide *when* to cancel, time out, pause, or retry (RM/Strategy/Recovery) |
| Surface output, progress, artifacts as facts (D/E/F) | Interpret, grade, or validate those facts (Validation, INV-20) |
| Report the process's terminal status (H) | Declare the *work* successful or failed-as-validated |
| Advertise what the runtime *can* do (A) | Decide what the runtime *should* do for a given package |
| Report *unknown* progress / *unsupported* capability honestly | Substitute a fabricated value to look more capable |

If removing a line of adapter reasoning would change *what* runs or *whether* it
succeeded, that line does not belong in the adapter (mirror of `01` §3). An adapter that
starts making selection, validation, or recovery decisions has stopped being a driver and
has absorbed responsibilities the platform spine forbids it from holding.

---

### Cross-references

- Adapters register descriptors into, and are discovered through, the Registry view —
  `04_RUNTIME_REGISTRY.md`.
- What an adapter *advertises* and how it is matched — `05_RUNTIME_CAPABILITIES.md`.
- Which runtime a package gets (selection + allocation) — `06_RUNTIME_SELECTION.md`.
- The lifecycle states an adapter's reports project onto — `07_RUNTIME_LIFECYCLE.md`.
- The only events an adapter's facts become — `15_RUNTIME_EVENTS.md`.
- Streaming, progress, artifacts, cancellation, timeouts, isolation —
  `08`, `12`, `13`, `09`, `10`, `17`.
