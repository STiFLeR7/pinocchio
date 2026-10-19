# 00 — Runtime Overview

**Status:** design only. This document fixes the subsystem's purpose, its inputs and
outputs, its position and dependency direction, the invariants it must honor, and the
**canon glossary** that every other Runtime document uses verbatim.

---

## 1. Purpose

The Runtime Manager (RM) takes an immutable **Execution Package** (a Harness output)
and **prepares a runtime to execute it**, then hands a prepared **Runtime Session** to
the Execution Engine. RM is the last subsystem before work actually runs. It is
**runtime-agnostic**: nothing in RM's core knows whether the runtime is Claude Code,
Gemini CLI, a shell, a Docker container, a browser driver, a Python process, an MCP
server, or a remote worker. All provider knowledge lives behind the **Runtime Adapter**
boundary (`03_RUNTIME_ADAPTERS.md`).

> RM **prepares** execution. The Execution Engine **performs** it. Validation decides
> whether the work actually succeeded (from Evidence, INV-20). RM never conflates these.

## 2. Inputs

RM consumes the outputs of the layers before it — **by value/reference, never by
reaching back into them**:

| Input | Produced by | Carries (relevant subset) |
|---|---|---|
| **Execution Package** | Harness (Phase 6) | embedded Work Package, immutable Context View, Skill refs, Capability requirements, Policy bundle, Artifact refs, Execution Strategy, metadata, correlation |
| **Execution Manifest** | Harness (Phase 6) | required capabilities/skills/artifacts/context, execution metadata, **capability-based** runtime requirements (`runtime_policy`), correlation |
| **Runtime Request** | Orchestration (Phase 5) | `runtime_policy`, `required_capability_refs`, **`candidate_harness_refs`** (candidates only, INV-37), coordination, correlation |
| **Runtime Registry view** | Harness Registry (ADR-002) | the `RUNTIME`-category descriptors: advertised capabilities, availability, health (INV-36) |

The Execution Package is the authority on *what to run*; the Runtime Request is the
authority on *which candidates are eligible and under what policy*; the Registry is the
authority on *which runtimes currently exist and are healthy*.

## 3. Outputs

| Output | Consumer | Notes |
|---|---|---|
| **Runtime Session** (prepared, allocated, bound, in state `Ready`) | Execution Engine (Phase 8) | the handoff artifact; RM owns its lifecycle throughout |
| **Runtime allocation** (a reservation in the Registry's `ResourceAllocationState`) | Registry / capacity accounting | `AVAILABLE → RESERVED → ALLOCATED → RELEASED` |
| **`runtime.*` events** | Event log (Phase 2) | event-sourced facts; session state is a projection (`15`) |
| **Telemetry / metrics / traces** | Observability (`16`) | health and session metrics; never the authoritative state |

RM does **not** output validated results, knowledge, recovery decisions, plans, or
context — those belong to other subsystems.

## 4. Position & dependency direction

```
nexus_runtime  →  { nexus_core, nexus_infra }      (the only imports)
        ▲
        │ consumes (by value/reference)
        └── Harness outputs (Execution Package / Manifest), Orchestration's Runtime Request
```

- RM **never** imports `nexus_planning`, `nexus_context`, `nexus_orchestration`, or
  `nexus_harness`. It consumes their *outputs*, exactly as each prior layer consumed
  the one before it.
- RM is imported by **nothing upstream**. The Execution Engine (downstream) consumes
  RM's Runtime Session.
- RM persists and emits **only** through the Phase 2 infrastructure substrate
  (event store, event bus, repositories, observability). It invents no new persistence
  mechanism and does not modify `nexus_infra` (the pattern every prior layer followed).
- The **only** place provider-specific code will ever live is inside individual Runtime
  Adapters (`03`, `19`). RM's core stays generic.

## 5. Responsibilities (and explicit non-responsibilities)

**RM is responsible for:** runtime discovery; runtime registration (as a Registry
view); capability matching; runtime health checks; runtime lifecycle; runtime
**allocation**; Runtime Session creation; runtime configuration; progress streaming;
timeout handling; cancellation; artifact collection; runtime telemetry.

**RM never:** plans work; orchestrates work; edits the repositories it reads from;
validates execution outcomes; performs recovery; updates Knowledge; or invokes AI
reasoning directly. (Adapters may *front* an AI runtime such as Claude Code, but RM's
core issues no prompts and makes no reasoning decisions — see `01` §Boundaries.)

## 6. Invariants RM must honor (existing, unchanged)

| Invariant / ADR | How RM honors it |
|---|---|
| **INV-09** runtimes receive Work Packages, never Goals | RM hands the Execution Package's embedded **Work Package** to the runtime; never a Goal or raw request |
| **INV-20** completion is from Evidence, not self-report | RM marks a session's *process* `Completed`; it never declares the *work* validated — Validation does |
| **INV-21** a Work Package never selects its own runtime | Selection happens in RM (`06`), within Orchestration's candidate set — never inside the package |
| **INV-32** Capabilities are provider-independent | Capability matching (`05`) compares abstract capabilities; provider identity enters only at adapter binding |
| **INV-36** the Harness Registry owns availability/health | RM **reads** availability/health from the Registry; it never duplicates or re-owns that state |
| **INV-37** Orchestration produces candidates, allocation is later | RM performs the **final selection + allocation** from `candidate_harness_refs` (`06`) |
| **INV-16** idempotent consumption | Every `runtime.*` event is keyed for dedupe; replay reproduces identical session state |
| **INV-17** timestamps are recorded data | Wall-clock values live only in event payloads; session value objects stay timestamp-free and deterministic |
| **ADR-001** event-sourced state | The Runtime Session's state is a **projection** of the `runtime.*` log; snapshots/checkpoints derive from it |
| **ADR-002** registries & capabilities | RM consumes the four registries; a "Runtime" is a Harness of category `RUNTIME` |
| **ADR-003** canonical object model, Evidence by reference | Artifacts emitted by runtimes are referenced by id (`13`), never embedded |
| **ADR-004** single approval taxonomy | RM **pauses** for approval (`14`) using the platform taxonomy; it never *decides* an approval |

## 7. Canon glossary (binding)

| Term | Meaning (fixed) |
|---|---|
| **Runtime Manager (RM)** | The subsystem that prepares runtimes and owns Runtime Sessions. Prepares; never performs. |
| **Runtime** | An integration boundary that can perform work — a Harness of category `RUNTIME` (doc 11 / ADR-002). |
| **Runtime Adapter** | The single conceptual contract a runtime satisfies so RM can drive it generically (`03`). |
| **Runtime Descriptor** | The Registry record for a runtime (reuses the Harness Registry's descriptor: advertised capabilities, availability, health, configuration). |
| **Runtime Registry** | The `RUNTIME`-category **view over the existing Harness Registry** — not a new store (`04`). |
| **Runtime Session** | The stateful instance binding one Execution Package to one allocated runtime for one execution attempt (`02`). |
| **Allocation** | Selecting + reserving a runtime from candidates; state via `ResourceAllocationState` = `AVAILABLE → RESERVED → ALLOCATED → RELEASED`. |
| **Execution Engine** | The downstream subsystem (Phase 8) that performs the work inside the runtime; out of scope here. |
| **Candidate** | A runtime advertised as capable of a required capability (from `RuntimeRequest.candidate_harness_refs`); a candidate is *eligible*, not *chosen*. |
| **Preparation** | Everything RM does to bring a session to `Ready`: select, allocate, configure, bind — but not run. |
| **Handoff** | The point where RM passes a `Ready` Runtime Session to the Execution Engine. |

## 8. One-paragraph mental model

A validated Plan became an Execution Graph and Strategy (Orchestration), which were
compiled into immutable Execution Packages (Harness). For each package, the Runtime
Manager looks at the Orchestration-supplied **candidates**, confirms each candidate's
**capabilities** satisfy the manifest, filters by **health/availability** (from the
Harness Registry), applies **governance/cost policy**, pauses for **approval** if
required, then **allocates** exactly one runtime and **creates a Runtime Session** that
binds the package to that runtime and configures it. The session reaches `Ready`. RM
hands it to the Execution Engine and then **supervises** — streaming output, enforcing
timeouts, honoring cancellation, collecting artifacts, emitting telemetry — until the
process ends, at which point RM releases the allocation and destroys the session.
**At no point does RM perform the work itself.**
