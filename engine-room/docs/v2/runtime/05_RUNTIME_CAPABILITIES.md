# 05 — Runtime Capabilities

**Status:** design only. Defines the **capability model and vocabulary** the Runtime
Manager (RM) uses to decide candidate eligibility: **required**, **optional**, and
**unsupported** capabilities; capability **negotiation**; and capability
**compatibility** (versioning). Capabilities are **provider-independent** (INV-32): they
come from the Execution Manifest's required capabilities matched against a candidate's
advertised capabilities.

This document defines the *model*, not the *selection logic*. Choosing one runtime from
the eligible set — and how optional capabilities weight that choice — is
`06_RUNTIME_SELECTION.md`. This file introduces no Protocol, class, algorithm, or API. It
cross-references its siblings by filename: `00_RUNTIME_OVERVIEW.md`,
`01_RUNTIME_MANAGER.md`, `03_RUNTIME_ADAPTERS.md`, `04_RUNTIME_REGISTRY.md`,
`06_RUNTIME_SELECTION.md`, `15_RUNTIME_EVENTS.md`.

---

## 1. Capabilities are provider-independent

Per INV-32, a Capability answers **"what can be done,"** never **"which provider does
it."** The grounding domain object (`nexus_core/domain/capability.py`) deliberately
omits provider, availability, and health; those live only on the Harness Registry
descriptor (INV-36, `04`). Capability matching therefore compares **abstract
capabilities to abstract capabilities** — provider identity enters only later, at adapter
binding (`00` §6; INV-32).

Two abstract sets meet during matching:

| Set | Where it comes from | Authority |
|---|---|---|
| **Required capabilities** | The **Execution Manifest** (Harness output), reflecting the package's needs and the `RuntimeRequest.required_capability_refs` (`nexus_orchestration/runtime_requests.py`) | *What the work needs* |
| **Advertised capabilities** | A candidate's Runtime Descriptor `advertised_capabilities` (`04`), references to abstract Capability definitions | *What a candidate offers* |

Matching is the act of comparing these two abstract sets. It produces the
`runtime.capabilities_matched` event (`15`) carrying required, satisfied, and unsupported
sets — and is RM's pipeline step 3 (`01`). Because both sides are provider-independent, a
brand-new runtime that advertises a known capability is matchable the moment it registers
(`03` §5, `04` §3).

## 2. The three capability classes

Every required-or-relevant capability falls into exactly one class for a given candidate.
This is the core vocabulary the rest of the subsystem reuses verbatim.

| Class | Definition | Effect on **eligibility** | Effect on **ranking** | Recorded as |
|---|---|---|---|---|
| **Required** | A capability the Manifest declares the work *must* have | **Decisive.** If any required capability is not satisfied, the candidate is **ineligible** | n/a — eligibility gate comes first | `required` + `satisfied` on `runtime.capabilities_matched` |
| **Optional** | A capability that is *desirable* but not mandatory (best-effort) | **None.** A missing optional never disqualifies a candidate | **Affects ranking** — a candidate that also satisfies optionals is preferable (policy in `06`) | part of the match result; consumed by `06` |
| **Unsupported** | A capability a candidate **cannot** satisfy | If it was **required** → contributes to ineligibility; if **optional** → may **degrade** the offering | A required-unsupported disqualifies; an optional-unsupported lowers rank | `unsupported` on `runtime.capabilities_matched` |

Two rules make this unambiguous:

1. **Required is an eligibility gate, optional is a ranking signal.** A candidate is
   *eligible* iff **all** required capabilities are satisfied. Optionals never gate
   eligibility — they only influence preference, and that influence is applied in `06`,
   not here.
2. **Unsupported is always recorded.** Whether a missing capability *disqualifies* (it was
   required) or merely *degrades* (it was optional), the fact that the candidate cannot
   satisfy it is **recorded** on the match result and `runtime.capabilities_matched`
   (`15`) — never silently dropped. This preserves the platform's no-silent-default
   discipline and gives `06`/`18` honest inputs.

```
   Manifest required caps ─┐
                           ▼
   For each candidate:  required satisfied?  ── no ──▶  INELIGIBLE (record unsupported-required)
                           │ yes
                           ▼
                       record optional satisfied / optional unsupported (best-effort)
                           │
                           ▼
                       ELIGIBLE candidate  ──▶  ranking inputs handed to 06
```

## 3. Negotiation

Some runtimes can satisfy a capability **only under conditions** — given a configuration,
a resource, a mode, or a degraded form. Negotiation is the model for expressing that,
*declaratively*, without RM core learning anything provider-specific.

- **What negotiation is:** a runtime (via its adapter, `03`) may **offer** a capability
  *conditionally* — e.g. "I can satisfy capability X **if** configured with Y," or "I can
  satisfy X in a **degraded** form." The offer is expressed as declarative facts on the
  descriptor/advertisement (`04`), not as code in RM.
- **What RM does with it:** RM treats a conditionally-offered capability as **satisfied
  only if its condition is met** by the configuration RM will render at `Prepared`
  (`01` step 10). If the condition cannot be met, the capability is **unsupported** for
  that candidate (§2) — recorded, then gating-or-degrading per its class.
- **Who decides:** RM evaluates whether a condition is *met*; it does **not** decide that
  a degraded offer is *acceptable* — that is selection/governance judgement (`06`/`18`).
  The adapter is a driver here too (`03` §6): it *offers* under conditions; it does not
  *choose* whether the offer is taken.
- **Honesty:** negotiation never lets an adapter fabricate a capability. An offer it
  cannot back is recorded as unsupported, not quietly counted as satisfied.

Negotiation thus stays in vocabulary terms — *offered*, *conditioned*, *satisfied*,
*degraded*, *unsupported* — and defers the *accept/reject* decision to `06`.

## 4. Compatibility (versioned capabilities)

Capabilities are **versioned** (ADR-002; the grounding `Capability` carries a `version`,
and descriptor advertisements are version-aware, `04`). Compatibility is the model for
matching across versions.

| Concept | Meaning | Consequence |
|---|---|---|
| **Versioned requirement** | The Manifest's required capability names a capability *and* a version expectation | A candidate must advertise a **compatible** version, not merely the same name |
| **Compatible advertisement** | A candidate advertises a version that satisfies the requirement's expectation (per ADR-002's versioning semantics) | Treated as **satisfied** |
| **Incompatible version** | A candidate advertises the capability name but at an incompatible version | Treated as **unsupported** (§2) for that requirement — recorded, then gates/degrades by class |
| **Unknown / unversioned** | Version cannot be determined | Resolved conservatively as **not compatible** (no silent assumption); recorded as such |

Rules:

- **Name match is not enough.** Compatibility is a name-*and*-version judgement, so the
  platform can evolve a capability definition without silently mis-binding old runtimes to
  new requirements (or vice versa).
- **Incompatibility is recorded as unsupported**, never papered over — same discipline as
  §2.
- **The compatibility *rule set* is ADR-002's**, not RM's invention; RM *applies* the
  versioning semantics, it does not define a new one.

## 5. Worked vocabulary (illustrative)

Illustrative only — not a schema, not selection logic. It shows the three classes,
negotiation, and compatibility producing one eligibility decision per candidate. (`06`
then ranks the eligible ones.)

| Candidate | Required: `code_generation`@v2 | Required: `file_write`@v1 | Optional: `progress_reporting` | Negotiated: `network_access` (if configured) | Eligibility | Notes for ranking (→ `06`) |
|---|---|---|---|---|---|---|
| Runtime A | satisfied (v2) | satisfied | satisfied | n/a | **Eligible** | satisfies an optional → preferable |
| Runtime B | satisfied (v2) | satisfied | unsupported | offered-if-configured → condition met → satisfied | **Eligible** | optional missing → lower rank than A |
| Runtime C | advertises v1 → **incompatible** → unsupported | satisfied | satisfied | n/a | **Ineligible** | required-unsupported (version) disqualifies |
| Runtime D | satisfied (v2) | unsupported | satisfied | n/a | **Ineligible** | required-unsupported disqualifies |

Every "unsupported" cell above is **recorded** on `runtime.capabilities_matched` (`15`),
whether it caused ineligibility (C, D) or merely a degraded/best-effort offering. The
match result hands `06` an honest picture: who is eligible, and how well each eligible
candidate covers the optionals.

## 6. What this model is *not*

- **Not provider-aware.** Matching compares abstract capabilities only (INV-32); provider
  identity enters at binding, never at matching.
- **Not selection.** It produces *eligibility* and *ranking inputs*; choosing one runtime
  is `06_RUNTIME_SELECTION.md`.
- **Not a place for silent defaults.** Unsupported and incompatible facts are recorded,
  never dropped.
- **Not the owner of availability/health.** A candidate can be perfectly capable yet
  filtered out for availability/health by the Registry (INV-36, `04`); capability
  eligibility and registry health are separate gates in the pipeline (`01` steps 3 and 4).

---

### Cross-references

- Where required/advertised capabilities come from and how they are advertised —
  `04_RUNTIME_REGISTRY.md`, `03_RUNTIME_ADAPTERS.md`.
- How eligible candidates and their optional coverage become one chosen runtime —
  `06_RUNTIME_SELECTION.md`; governing policy — `18_RUNTIME_GOVERNANCE.md`.
- The event that records the match (required / satisfied / unsupported) —
  `15_RUNTIME_EVENTS.md` (`runtime.capabilities_matched`).
- The pipeline position of matching — `01_RUNTIME_MANAGER.md` (step 3).
