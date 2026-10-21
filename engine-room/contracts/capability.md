# Capability — Canonical Logical Contract

Status: Frozen (Phase 0 contract freeze)
Object: Capability · Primary source: `docs/v2/21_CAPABILITY_MODEL.md` · Binding ADRs: ADR-002

> A logical, implementation-independent specification. Fields are logical
> (name + meaning + required/optional), never wire/typed definitions. No
> serialization, storage, API, or code is implied here.

---

## 1. Purpose

A Capability is the abstract definition of **what operational outcome can be
produced** — independent of *who* performs it or *how* it is implemented. It is
the stable unit of functionality that Planning reasons about before any provider,
runtime, or skill is considered.

A Capability answers "what can be done" and never "which provider does it." It is
the platform's currency for provider-independent reasoning: capabilities remain
stable while runtimes, skills, and providers evolve beneath them (`21`).

---

## 2. Ownership

- **Produced / owned by:** the **Capability Registry** (per ADR-002, the
  authoritative registry of abstract capability *definitions*). Definitions are
  versioned, append-only, and provider-independent.
- **State transitions owned by:** the Capability Registry alone (registration,
  versioning, deprecation of definitions). A Capability definition carries **no
  operational/runtime state**; it has no per-execution lifecycle.
- **Consumed by:**
  - **Planning** — reasons in required Capabilities when decomposing Goals
    (Planning never executes — INV-03).
  - **Capability Resolution** (Phase 3, AP-304) — a *read* across the Capability
    Registry ∪ Harness Registry that returns candidate providers. Resolution
    returns **candidates only**; it never selects a runtime (INV-37).
  - **Orchestration** — performs selection/allocation over the returned
    candidates (INV-37); selection is Orchestration's, never Resolution's.
- **Explicitly NOT owned here:** provider identity, availability, and health.
  Those are owned solely by the **Harness Registry** (ADR-002 field-ownership
  table; INV-32, INV-36). A Capability never embeds provider state.

---

## 3. Lifecycle

A Capability **definition** is a versioned, append-only catalog entry, not a
per-operation runtime object. Its definitional states (a projection of registry
events per ADR-001) are:

```
Draft → Registered → Active → Deprecated → Retired
```

- **Draft** — authored but not yet published to the registry.
- **Registered / Active** — published and resolvable by Capability Resolution.
- **Deprecated** — superseded by a newer version; still resolvable for existing
  references, but discouraged for new plans.
- **Retired** — no longer offered for new resolution; historical references
  remain replayable (event upcasting, ADR-001).

There is **no** Allocated / InUse / Failed / Available state on a Capability —
those are allocation-projection and provider-health concerns owned elsewhere
(`resource.md`, Harness Registry). Versions are immutable once published; change
means a new version, never in-place mutation.

---

## 4. Required Fields

| Field | Meaning |
|-------|---------|
| **Identifier** | Stable, globally unique identity of the Capability, independent of any provider. Participates in correlation/trace lineage. |
| **Name** | Human-readable operational name (e.g. "Repository Analysis", "Code Generation"). |
| **Version** | Definition version. Capabilities evolve independently; references are version-aware (`21`). |
| **Category** | Logical grouping of the functionality (e.g. Analysis, Development, Documentation, Communication, Operations, Knowledge) — taxonomy only, no provider meaning. |
| **Description** | What operational outcome the Capability produces; the one functional job it names. |
| **Inputs** | Logical declaration of the information the Capability requires to produce its outcome (named, with logical meaning/role). Logical "typed-ish" shape only — not a wire schema. |
| **Outputs** | Logical declaration of the operational outcome(s) produced (named, with logical meaning/role). Logical shape only. |

---

## 5. Optional Fields

| Field | Meaning |
|-------|---------|
| **Constraints** | Abstract operational boundaries inherent to the capability: required context, security requirements, governance requirements, resource requirements, validation requirements, execution constraints (`21`). Declarative and provider-independent; enforcement lives in Governance/Orchestration. |
| **Dependencies** | Other Capabilities this one logically requires or composes with (supports capability composition, `21`). References by Capability Identifier/version. |
| **Metadata** | Non-authoritative descriptive attributes (tags, ownership notes, documentation links, measurement/observability hints). Carries no operational truth. |

> Note: "Provider", "Availability", and "Health" — though listed in the doc-21
> registry sketch — are **deliberately excluded** from this contract and assigned
> to the Harness Registry (ADR-002; INV-32). They are not optional fields here.

---

## 6. Invariants

- **INV-32** — Capabilities remain provider-independent: a Capability defines
  *what* can be done with **no provider, health, or availability state**; that
  state lives only in the Harness Registry. *(Binding for this contract.)*
- **INV-36** — There is one source of truth for provider availability/health (the
  Harness Registry); this contract references it, never duplicates it.
- **INV-37** — Capability Resolution returns **candidates only**; runtime
  selection is Orchestration's. A Capability definition never selects a provider.
- **INV-07** — Exactly one canonical schema per object: the Capability is defined
  only here; no subsystem introduces an alternative representation.
- **INV-03 / INV-02** — Planning consumes Capabilities to decide *what* work
  happens; the Capability Model never executes, plans, validates, or selects
  providers (`21` Architectural Boundaries).
- **Composition closure** — every entry in *Dependencies* references a Capability
  that exists in the Capability Registry (no dangling capability references).
- **Versioning immutability** — a published `(Identifier, Version)` pair is never
  mutated in place (ADR-001 additive evolution).

---

## 7. Relationships

- **`skill.md`** — A Skill *requires* one or more Capabilities; one Capability may
  support many Skills (`21`, `06`). Skills are procedures; Capabilities are
  functionality — the two are distinct objects (ADR-002 §D).
- **Harness Registry** (documented in the Harness SDK spec, not a contract file
  here) — Harnesses *advertise* Capabilities they can provide; the Harness
  Registry holds the provider/availability/health for those advertisements.
  Capability Resolution reads across this contract ∪ the Harness Registry.
- **`resource.md`** — A harness-backed Resource references advertised
  Capabilities **via the Harness Registry**; it never re-defines or duplicates
  Capability definitions.
- **`plan.md`** — A Plan references *Required Capabilities* (by Identifier +
  version) as the abstract demand Planning emits before resolution/allocation.
- **`execution_strategy.md`** — consumes resolved capability candidates as the
  basis on which it declares coordination behavior (it does not define
  Capabilities).

---

## 8. Versioning Rules

- Evolution is **additive**: new optional fields, new Capability versions, or new
  Capabilities. Published `(Identifier, Version)` definitions are immutable.
- A **new Version** is required for any change to logical Inputs/Outputs meaning,
  Constraints semantics, or Dependencies that could alter what a consumer expects
  the outcome to be.
- **Category** and **Metadata** taxonomy may be extended additively without a new
  object version, provided no existing consumer guarantee changes.
- Old versions remain **resolvable and replayable** until Retired; historical
  references in past plans/events stay valid forever (ADR-001 event upcasting).
- Capabilities version **independently** of providers, skills, and runtimes
  (`21`); provider support for a version is advertised in the Harness Registry,
  never recorded on the Capability.
