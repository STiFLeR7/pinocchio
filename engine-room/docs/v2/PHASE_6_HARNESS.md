# Phase 6 — Harness Layer: Implementation Decisions

**Status:** Implemented. **Scope:** the harness layer (`nexus_harness/`).
**Authority:** This document records *implementation decisions* only. It does not
amend any ADR, contract, or invariant — the architecture remains frozen.
Observations that might warrant future architecture review are listed in §5 with
recommendations, not applied.

The Harness **compiles**; it never executes. Given the Harness Requests an
Orchestration cycle produced, it validates them and resolves their Skills,
Capabilities, Policies, Context, and Artifacts into immutable, runtime-ready
**Execution Packages** and descriptive **Execution Manifests** — then persists them
through Phase 2 infrastructure and emits harness events. With Phase 6 the pipeline
reaches the permanent compilation boundary, the last preparation stage before
runtime selection and execution:

```
… → Orchestration → Harness → Execution Package → (Runtime Manager → Execution Engine)
```

---

## 1. Component → architecture mapping

| Component (`nexus_harness/…`) | Produces / does | Doc 11 / Invariants |
|---|---|---|
| `harness.HarnessService` | drives the pipeline, persists, emits | doc 11 boundaries |
| `validator` | Step 1 — validate + resolve the primary references | fail-fast |
| `skill_resolver` | Step 2 — resolved Skill references | INV-33 |
| `capability_resolver` | Step 3 — Capability requirements (provider-independent) | INV-32, INV-37 |
| `policy_resolver` | Step 4 — deterministic policy bundle (no evaluation) | ADR-004 |
| `context_resolver` | Step 5 — immutable Context View | INV-06/12 |
| `artifact_resolver` | Step 6 — resolved input Artifacts (read-only) | ADR-003, INV-12 |
| `package_builder` | Step 7 — immutable Execution Package | doc 11 *Outputs* |
| `manifest_builder` | Step 8 — descriptive Execution Manifest | doc 11 *Outputs* |
| `sources` | resolution providers + reference registries | ADR-002 |
| `validators` | error hierarchy + pure validation functions | fail-fast |
| `composition` | DI wiring over `nexus_infra` | — |

## 2. Key implementation decisions

1. **Deterministic, AI-free compilation.** The work arrives as immutable Harness
   Requests; the Harness resolves and assembles them mechanically. Every identifier
   is a pure function of the Harness Request identity (`ids.py`), so identical
   Harness Requests and identical resolution sources yield byte-identical Execution
   Packages, Execution Manifests, and event streams. There is no AI and no
   randomness, and no timestamp appears in any identifier (INV-17).

2. **Compile, never execute.** The Harness resolves *references into definitions*
   and packages them. It never invokes an LLM, edits a repository it reads from,
   runs a shell/Git command, allocates a runtime, executes a Work Package, performs
   recovery, or validates an outcome (doc 11 *Architectural Boundaries*). The
   Runtime Manager — the next phase — executes the packages.

3. **Fail-closed resolution.** Every reference (Work Package, Context Package,
   Execution Strategy, Skills, Capabilities, explicitly-referenced Policies,
   Artifacts) must resolve against its source/registry; a dangling reference raises
   `UnresolvedReferenceError` and the cycle emits `harness.failed` and raises.
   Nothing is invented, defaulted, or silently dropped (INV-30 fail-closed posture).

4. **Capability requirements are the union of request + Skills.** A node's required
   capabilities are the capabilities named on the Harness Request unioned with the
   capabilities each resolved Skill declares it needs — deduplicated and sorted.
   Capabilities are resolved as provider-independent metadata only; no provider is
   selected and no runtime is allocated (INV-32 / INV-37).

5. **Policies are gathered, never evaluated.** The Policy Resolver bundles the
   platform's enabled governance policies plus any policy a request constraint
   references explicitly, and carries the Strategy's declared approval taxonomy. It
   computes no decision and produces no outcome — evaluation is the Policy Engine's
   (ADR-004: declaration ≠ evaluation; recovery strategies are never Policy
   Decisions).

6. **Context is projected into an immutable view, never modified.** The Context
   Resolver folds the resolved Context Package into a frozen `ContextView` carried
   by value, so a runtime cannot reach back and mutate the source Context Package
   that Context Engineering owns.

7. **The Execution Package contains everything Runtime requires — and nothing more.**
   It embeds the Work Package (runtimes receive Work Packages, INV-09), the Context
   View, Skill references, Capability requirements, the Policy bundle, input
   Artifact references, the Execution Strategy, descriptive metadata, and the
   correlation lineage. The Execution Manifest is its flat, **descriptive** companion
   — required capabilities/skills/artifacts/context, execution metadata, and
   capability-based runtime requirements (from the Strategy's `runtime_policy`, which
   never names a runtime). The manifest is never executable.

8. **Reuse of the Phase 2 persistence mechanism.** Execution Packages and Manifests
   are persisted through instances of the same Phase 2 `InMemoryRepository` generic;
   the resolution sources reuse the same generic (and the infrastructure's own
   Artifact repository); the emitter is the infrastructure context. No new
   persistence mechanism was created and `nexus_infra` was not modified.

9. **Injected, deterministic event timestamps.** Emitted events carry a timestamp
   from an injected `TimestampSource` (fixed in tests). The produced *value objects*
   (Packages, Manifests, Views) carry no timestamp, so they stay deterministic
   regardless of the clock (INV-17).

## 3. What was deliberately NOT built (out of scope)

Runtime allocation and execution, the Runtime Manager, the Execution Engine, AI
providers, Claude/Gemini integration, shell/Git operations, repository editing,
Policy *evaluation*, Validation, Recovery, Knowledge, Reflection, scheduling, and
APIs. The Harness's outputs (Execution Packages + Manifests) are the inputs to the
Runtime Manager that follows; it consumes the infrastructure without modifying it.

## 4. Validation gate (all met)

| Gate criterion | Result |
|---|---|
| Harness Requests validated | ✅ shape + primary references resolved, fail-closed |
| Skills resolved | ✅ resolved references + metadata; capability refs separated |
| Capabilities resolved | ✅ request ∪ Skill-implied, deduped/sorted, provider-independent |
| Policies resolved | ✅ deterministic bundle, gathered not evaluated (ADR-004) |
| Context resolved | ✅ immutable execution view; source never modified |
| Artifacts resolved | ✅ input Artifact references, read-only, fail-closed |
| Execution Packages created | ✅ immutable, runtime-ready, one per Harness Request |
| Execution Manifests created | ✅ descriptive, never executable, one per package |
| Events emitted | ✅ validated/skills/capabilities/policies/context/artifacts/package/manifest/completed, failed-on-error |
| Persistence succeeds | ✅ via Phase 2 repositories |
| Existing phases remain green | ✅ 193 + 180 + 149 + 156 + 217 unchanged |
| No architectural invariant violated | ✅ no ADR/contract/`nexus_core`/`nexus_infra` change |

Coverage: `nexus_harness` 100% (branch), ≥95 floor. Full suite: `mypy --strict`
clean, `ruff` clean.

## 5. Design observations (for future architectural review — NOT applied)

- **O-10 — Execution Package / Execution Manifest / Context View have no frozen core
  contract.** Doc 11 lists Execution Packages and Manifests as Harness *outputs*, but
  `nexus_core` defines no contract/domain model for them, so they ship as
  harness-layer value objects (as Execution Sessions / Harness Requests did for
  Orchestration — O-7). *Recommendation:* if these objects need to cross layers (the
  Runtime Manager will consume Execution Packages, supervision may read manifests), a
  future contract-freeze pass should promote them to ratified contracts. Low urgency.

- **O-11 — Reference registries for Skills, Capabilities, and Policies have no
  dedicated home yet (mirrors O-3/O-6/O-8).** No registry phase exists, so
  deterministic reference `InMemorySkillRegistry` / `InMemoryCapabilityRegistry` /
  `InMemoryPolicyRegistry` (implementing the frozen ADR-002 Protocols) ship in
  `nexus_harness`. Every resolver depends only on the Protocol (dependency
  inversion), so they are swappable. *Recommendation:* a future Registry phase (or a
  `nexus_infra` extension) should own the concrete registries; the Harness would
  consume them by injection. Low urgency.

- **O-12 — Work Package / Context Package / Execution Strategy resolution reuses the
  Phase 2 repository generic as a read seam.** The Harness resolves these three
  primary objects through injected `Repository[T]` seams (the Phase 2
  `InMemoryRepository`), populated by the upstream layers that produced them. This
  keeps the Harness reference-based and decoupled, but the seam currently assumes the
  caller has persisted those objects. *Recommendation:* once a cross-layer object
  store or the Registry phase exists, wire these sources to it. No action now.

These observations do not block Phase 6 or require action now.
