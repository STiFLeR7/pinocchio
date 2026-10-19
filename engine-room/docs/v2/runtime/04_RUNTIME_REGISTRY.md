# 04 — Runtime Registry

**Status:** design only. Defines the **Runtime Registry** as the `RUNTIME`-category
**view over the existing Harness Registry** — not a new store. It describes the
*responsibilities* of registration, discovery, capability advertisement, health
reporting, availability, and prioritization — never an algorithm. Where a ranking
*policy* is implied, it is deferred to `06_RUNTIME_SELECTION.md` and
`18_RUNTIME_GOVERNANCE.md`.

This document introduces no Protocol, class, or API. It cross-references its siblings by
filename: `00_RUNTIME_OVERVIEW.md`, `01_RUNTIME_MANAGER.md`, `02_RUNTIME_SESSION.md`,
`03_RUNTIME_ADAPTERS.md`, `05_RUNTIME_CAPABILITIES.md`, `06_RUNTIME_SELECTION.md`,
`07_RUNTIME_LIFECYCLE.md`, `15_RUNTIME_EVENTS.md`.

---

## 1. There is no second registry

The single most important rule of this document:

> The **Runtime Registry is a VIEW** — the `RUNTIME`-category projection over the
> **existing Harness Registry** (ADR-002). RM invents **no** new registry, store, or
> ownership of availability/health.

Per INV-36, the Harness Registry is the **sole owner** of provider `availability` and
`health`. The grounding contract (`nexus_core/registries/interfaces.py`) defines the
`HarnessRegistry` and the `HarnessDescriptor`, and the `HarnessCategory` enum whose
`RUNTIME` member identifies a runtime (`00` §7; ADR-002). RM **reads** this registry;
**adapters register into it** (`03`). Nothing in RM re-owns, duplicates, or re-derives
availability/health.

```
        Harness Registry (existing, INV-36 owner of availability/health)
        ┌───────────────────────────────────────────────────────────────┐
        │  HarnessDescriptor: RUNTIME │ CONTEXT │ KNOWLEDGE │ VALIDATION  │
        │                    COMMUNICATION │ GOVERNANCE │ OBSERVABILITY    │
        └───────────────────────────────────────────────────────────────┘
                              │  filter: category == RUNTIME
                              ▼
        Runtime Registry VIEW (this document) ── read by RM ── (03 adapters write in)
```

The "Runtime Registry" is therefore a lens, not a database. Every responsibility below is
either a *read through that lens* (RM's side) or a *registration into the underlying
store* (the adapter's side).

## 2. The Runtime Descriptor (what a runtime carries)

A runtime is described by the existing `HarnessDescriptor` (grounding:
`nexus_core/registries/interfaces.py`), seen through the `RUNTIME` lens. RM defines **no
new descriptor type**. The fields RM relies on:

| Descriptor field | Carries | Owner / source | RM uses it for |
|---|---|---|---|
| `identity` | Stable runtime identity | Adapter at registration | Resolving `candidate_harness_refs` (`06`); deriving allocation id (`02`) |
| `category` | `HarnessCategory.RUNTIME` | Adapter | The filter that *defines* this view (§3) |
| `version` | Descriptor/runtime version | Adapter | Versioned capability compatibility (`05`, ADR-002) |
| `advertised_capabilities` | References to abstract Capability definitions | Adapter (`03`/`05`) | Capability matching (`05`) — provider-independent (INV-32) |
| `availability` | `ResourceAvailability` (AVAILABLE, BUSY, RESERVED, OFFLINE, MAINTENANCE, FAILED, UNKNOWN) | **Harness Registry (INV-36)** | Health/availability filtering (§5; pipeline step 4, `01`) |
| `health` | `ResourceAvailability` health projection | **Harness Registry (INV-36)** | Dropping unhealthy candidates (§5) |
| `configuration` | The runtime's declared configuration shape | Adapter | Rendering adapter config at `Prepared` (`01` step 10) |
| `metadata` | Non-authoritative descriptive attributes (incl. declarative prioritization hints, §7) | Adapter | Inputs to the selection *policy* (deferred to `06`) |

The descriptor is **advertised, by reference, never embedded** — `advertised_capabilities`
are references to abstract Capability definitions in the Capability Registry, never copies
(INV-32; `nexus_core/domain/capability.py` deliberately omits provider/availability/health).

## 3. Registration & discovery (responsibilities)

### Registration — the adapter's side

- An adapter **registers a Runtime Descriptor** into the Harness Registry with
  `category = RUNTIME`, advertising the runtime's identity, version, and the abstract
  capabilities it can satisfy (`03` concern A, `05`).
- Registration is the *only* way a runtime becomes visible to RM. RM does not "install"
  runtimes; it discovers whatever has registered. This is what keeps unknown future
  runtimes addable without touching RM core (`19`).
- Registration declares *what the runtime can do and how it is configured* — never *what
  it should do for a package* (that is selection, `06`, INV-21).

### Discovery — RM's side

- **Discovery filters to the `RUNTIME` category.** The Runtime Registry view is exactly
  "all descriptors where `category == RUNTIME`." RM never discovers context, knowledge,
  validation, governance, or observability harnesses through this lens.
- For a given preparation, RM **does not freely browse** all runtimes. It resolves the
  Orchestration-supplied `candidate_harness_refs` (INV-37; `RuntimeRequest`,
  grounding: `nexus_orchestration/runtime_requests.py`) **against** the view to obtain
  the candidate descriptors (pipeline step 2, `01`). Discovery is candidate-scoped.
- Discovery is a **read**. RM edits nothing in the registry it reads from (`01` §3). The
  one record RM *does* own — the allocation reservation — is RM's own state, tracked in
  `ResourceAllocationState` (`06`), not a mutation of registry-owned availability/health.

The act of resolving candidates emits `runtime.candidates_resolved` (`15`); the act of
matching their capabilities emits `runtime.capabilities_matched` (`15`, `05`).

## 4. Capability advertisement

- A runtime advertises capabilities by listing **references to abstract Capability
  definitions** in its descriptor's `advertised_capabilities` (INV-32: capabilities are
  provider-independent; the provider identity is on the *descriptor*, not on the
  Capability).
- Advertisement answers "what can this runtime do," in the platform's shared capability
  vocabulary. It is the input to matching (`05`): RM keeps a candidate only if its
  advertised capabilities satisfy the Execution Manifest's required capabilities
  (`01` step 3).
- Capabilities are **versioned** (ADR-002); advertisement therefore carries enough to
  reason about compatibility, with the compatibility *model* defined in `05` and the
  matching outcome recorded on `runtime.capabilities_matched` (`15`).
- The Registry view advertises; it does **not** rank. Which advertised-and-matched
  candidate is chosen is selection policy, deferred to `06`.

## 5. Health & availability reporting (and who owns them)

Ownership is unambiguous and fixed by INV-36:

| Concern | Owner | RM's role |
|---|---|---|
| `availability` (`ResourceAvailability`) | **Harness Registry** | **Reads** it; filters out non-available candidates (`01` step 4) |
| `health` (`ResourceAvailability`) | **Harness Registry** | **Reads** it; drops unhealthy candidates |
| Liveness *signal* from a running runtime | The runtime, via its adapter (`03`) | **Probes/observes** it as `runtime.heartbeat` (`15`, `10`); never promotes it to authoritative registry state |

- RM **never writes** availability or health. It reads the projection the Harness
  Registry owns. A runtime that is `BUSY`, `RESERVED`, `OFFLINE`, `MAINTENANCE`, or
  `FAILED` is filtered out of candidacy by RM at preparation time — but the *reason* it
  has that availability is the registry's truth, not RM's.
- RM **may probe** a runtime's own health signal **through the adapter** while a session
  runs, and surface it as telemetry/heartbeat (`16`, `10`). This is observation, **not**
  ownership: telemetry is never treated as authoritative state (`01` §4; `15` §4). If a
  runtime's *registry* availability must change, that change happens in the
  Harness Registry per INV-36 — RM only consumes the result.
- The distinction between `availability` (is it offered/free?) and `health` (is it well?)
  is preserved exactly as the grounding descriptor models it; RM does not merge them.

## 6. Allocation is RM's, availability is the registry's

A boundary worth stating explicitly because the two are easily confused:

| State machine | Vocabulary | Owner | Meaning |
|---|---|---|---|
| **Availability** | `ResourceAvailability` (AVAILABLE…UNKNOWN) | **Harness Registry (INV-36)** | The runtime's offered/health condition — a fact RM reads |
| **Allocation** | `ResourceAllocationState` (AVAILABLE → RESERVED → ALLOCATED → RELEASED) | **Runtime Manager** | RM's reservation of a chosen runtime for one session (`02`, `06`) |

RM **reserves and allocates** a runtime it selected from the candidate set
(`06`; INV-37), tracking that in `ResourceAllocationState`, and **releases** it at
teardown so capacity is never leaked (`07` §6). This is RM's own bookkeeping; it does not
overwrite the registry-owned `availability`. Allocation lives in RM; availability/health
live in the registry. (`runtime.allocated` and `runtime.released` record the allocation
transitions — `15`.)

## 7. Prioritization (declarative inputs only; policy deferred)

The Registry view **does not rank runtimes**, and this document defines **no ranking
algorithm**. It defines only the *inputs* and *responsibility*:

- **Inputs available for prioritization** are declarative facts surfaced by the view and
  the request: advertised capabilities and their match/optional results (`05`);
  registry-owned `availability`/`health`; descriptor `metadata` (which may carry
  declarative prioritization hints — e.g. cost class, preference weight, locality —
  expressed as data, never as code); and the `runtime_policy` carried on the
  `RuntimeRequest` (`nexus_orchestration/runtime_requests.py`) and the Execution Strategy
  (`18`).
- **Responsibility:** the Registry view *exposes* these inputs; it does not *act* on them.
- **Where the policy lives:** turning these declarative inputs into a single chosen
  runtime is **selection**, defined in `06_RUNTIME_SELECTION.md`, governed by policy in
  `18_RUNTIME_GOVERNANCE.md`. Prioritization is therefore expressed *declaratively* (as
  hints/weights/policy data) and *applied* in `06` — never hard-coded in the Registry or
  in RM core.

This keeps the view free of judgement: it tells RM *what exists, what each can do, and
how each is faring*, and stops there. Selection (`06`) decides; the view only informs.

## 8. What the Runtime Registry is *not*

- **Not a new store.** It is the `RUNTIME`-category view over the Harness Registry
  (ADR-002, INV-36).
- **Not the owner of availability/health.** The Harness Registry owns those (INV-36); RM
  reads them.
- **Not a selector or ranker.** It advertises candidates only (INV-37); selection and
  prioritization policy are `06`/`18`.
- **Not writable by RM** (except RM's own allocation bookkeeping, which is not registry
  state).
- **Not a place for provider-specific code.** That lives behind adapters (`03`); the
  view holds only descriptors and references.

---

### Cross-references

- Who registers into the view, and the driver contract — `03_RUNTIME_ADAPTERS.md`.
- The capability model the descriptors advertise into — `05_RUNTIME_CAPABILITIES.md`.
- Turning candidates + declarative inputs into one chosen, allocated runtime —
  `06_RUNTIME_SELECTION.md`; governing policy — `18_RUNTIME_GOVERNANCE.md`.
- Allocation lifecycle and teardown/release — `02_RUNTIME_SESSION.md`,
  `07_RUNTIME_LIFECYCLE.md`.
- The events that record resolution/match/allocation/release —
  `15_RUNTIME_EVENTS.md`.
