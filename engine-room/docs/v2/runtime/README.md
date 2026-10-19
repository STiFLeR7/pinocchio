# Nexus v2 — Runtime Manager Architecture (Phase 7, design only)

> **Status:** Architecture & design specification. **No implementation.** This
> directory defines *what* the Runtime Manager is and *how* it must behave, so that a
> future implementation team can build it without making new architectural decisions.
> It introduces **no** production code, Protocols, classes, algorithms, adapters, or
> APIs. It amends **no** ADR, contract, or invariant; where the existing architecture
> needs clarification, that is recorded as a *recommendation* in
> [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md), not applied.

## Why this exists

Nexus has reached its **permanent execution boundary**. Six layers prepare work but
never run it:

```
Goal → Context Engineering → Planning → Orchestration → Harness → ▮ Runtime Manager ▮ → Execution Engine
                                                         (compiles)   (prepares)          (performs)
```

The Harness compiles an immutable **Execution Package** (everything a runtime needs)
and a descriptive **Execution Manifest**. The Runtime Manager answers exactly one
question:

> Given an immutable Execution Package, how does Nexus **prepare a runtime for
> execution** while remaining completely **runtime-agnostic** — supporting Claude
> Code, Gemini CLI, Shell, Docker, Browser, Python, MCP servers, remote workers, and
> runtimes not yet imagined — without architectural compromise?

**Runtime Manager prepares execution. The Execution Engine performs execution. These
responsibilities never merge.** That single sentence is the spine of every document
here.

## The boundary, stated precisely

| Concern | Owner |
|---|---|
| Decide *what* work exists | Planning (Phase 3) |
| Assemble *operational understanding* | Context Engineering (Phase 4) |
| Decide *coordination & order*, produce runtime **candidates** | Orchestration (Phase 5) |
| Compile a runtime-ready, immutable **Execution Package** | Harness (Phase 6) |
| **Select + allocate a runtime, create & supervise a Runtime Session, prepare it for execution** | **Runtime Manager (Phase 7)** |
| Actually run the work inside the runtime | Execution Engine (Phase 8, future) |
| Determine *real* completion from Evidence | Validation (future) |
| Recover from failure | Recovery (future) |
| Learn from outcomes | Knowledge / Reflection (future) |

## Reading order

| # | Document | Defines |
|---|---|---|
| — | [`00_RUNTIME_OVERVIEW.md`](00_RUNTIME_OVERVIEW.md) | The subsystem, its inputs/outputs, dependency direction, and the canon glossary |
| — | [`01_RUNTIME_MANAGER.md`](01_RUNTIME_MANAGER.md) | The Manager's responsibilities, the prepare pipeline, and hard boundaries |
| — | [`02_RUNTIME_SESSION.md`](02_RUNTIME_SESSION.md) | The Runtime Session: identity, ownership, state, retries, checkpoints |
| — | [`03_RUNTIME_ADAPTERS.md`](03_RUNTIME_ADAPTERS.md) | The conceptual adapter contract every runtime satisfies |
| — | [`04_RUNTIME_REGISTRY.md`](04_RUNTIME_REGISTRY.md) | Registration, discovery, health, availability, prioritization |
| — | [`05_RUNTIME_CAPABILITIES.md`](05_RUNTIME_CAPABILITIES.md) | Required / optional / unsupported capabilities, negotiation |
| — | [`06_RUNTIME_SELECTION.md`](06_RUNTIME_SELECTION.md) | Candidate → selection → **allocation**; where Orchestration stops |
| — | [`07_RUNTIME_LIFECYCLE.md`](07_RUNTIME_LIFECYCLE.md) | The canonical session state machine and transitions |
| — | [`08_STREAMING_MODEL.md`](08_STREAMING_MODEL.md) | Runtime-independent streaming of stdout/stderr/events/progress |
| — | [`09_CANCELLATION_MODEL.md`](09_CANCELLATION_MODEL.md) | Graceful / forced cancellation, escalation, cleanup |
| — | [`10_TIMEOUT_MODEL.md`](10_TIMEOUT_MODEL.md) | Execution / inactivity / policy / heartbeat timeouts |
| — | [`11_ERROR_MODEL.md`](11_ERROR_MODEL.md) | Error taxonomy and ownership |
| — | [`12_PROGRESS_MODEL.md`](12_PROGRESS_MODEL.md) | Progress events, phases, milestones, unknown progress |
| — | [`13_ARTIFACT_MODEL.md`](13_ARTIFACT_MODEL.md) | Runtime-independent artifact/log/metric emission |
| — | [`14_APPROVAL_CALLBACKS.md`](14_APPROVAL_CALLBACKS.md) | Pausing for approval/governance without depending on UI |
| — | [`15_RUNTIME_EVENTS.md`](15_RUNTIME_EVENTS.md) | The canonical `runtime.*` event taxonomy |
| — | [`16_RUNTIME_OBSERVABILITY.md`](16_RUNTIME_OBSERVABILITY.md) | Telemetry, tracing, metrics, health, session metrics |
| — | [`17_RUNTIME_SECURITY.md`](17_RUNTIME_SECURITY.md) | Sandboxing, filesystem, credentials, isolation, least privilege |
| — | [`18_RUNTIME_GOVERNANCE.md`](18_RUNTIME_GOVERNANCE.md) | Policy/approval/audit checkpoints and ownership |
| — | [`19_RUNTIME_EXTENSIBILITY.md`](19_RUNTIME_EXTENSIBILITY.md) | Adding runtimes without touching upstream layers |
| — | [`20_RUNTIME_GAPS.md`](20_RUNTIME_GAPS.md) | Open questions and deferred decisions |
| — | [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md) | Correctness, scalability, risks, and any recommended Phase-0 clarifications |

## Canon (binding for every document)

These terms and rules are **fixed** in `00`/`01`/`02`/`07`/`15`. No document may
redefine them, invent a parallel lifecycle, or coin a competing event name:

- **Runtime Manager (RM)** — the subsystem specified here. Prepares; never performs.
- **Runtime Adapter** — the single conceptual contract every runtime satisfies (`03`).
- **Runtime** — a Harness of category `RUNTIME` (ADR-002 / doc 11). The Runtime
  Registry is the `RUNTIME`-category **view over the existing Harness Registry**
  (INV-36 owner of availability/health) — RM invents **no** second registry.
- **Runtime Session** — the stateful instance binding one Execution Package to one
  allocated runtime for one execution attempt (`02`).
- **Execution Engine** — performs the work inside the runtime (Phase 8, out of scope).
- **Allocation** — selecting + reserving a runtime from Orchestration's candidates,
  tracked by `ResourceAllocationState` (`AVAILABLE → RESERVED → ALLOCATED → RELEASED`).
- **Dependency direction** — `nexus_runtime → {nexus_core, nexus_infra}` only; it
  consumes Harness/Orchestration outputs by value/reference and is imported by nothing
  upstream (`00`).
