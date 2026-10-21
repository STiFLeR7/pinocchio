# Gaps & Deferred Decisions

Status: Target Architecture (design only)

---

# Purpose

This document names every open question, deferred decision, and frontier concern in the Engineering
Intelligence architecture. Naming them is the discipline that lets the core be ratified now: nothing
below blocks implementation of the core; each is a defined extension point, not a silent assumption.

---

# G1 — The Engineering Strategy contract

**Open:** The `Engineering Strategy` needs a frozen contract (proposed
`contracts/engineering_strategy.md`), defining each facet's schema.

**Deferred because:** contracts are frozen by ADR/Phase-0 authority, not by a design package. This
package specifies the *shape and semantics* (`04`); ratifying the *contract file* is a Phase-0 act.

**Non-blocking:** the facets are fully specified here; a contract is a faithful transcription, not a
new decision. Recommended in `ARCHITECTURE_REVIEW.md`.

---

# G2 — Repository Intelligence as its own package

**Open:** Repository Intelligence deserves a full architecture package (`docs/v2/repository/`), the
way Knowledge and Runtime have theirs.

**Deferred because:** this package specifies Repository Intelligence only to the depth EI needs to
consume it, and fixes the ownership verdict (separate subsystem, `10`). The indexing model, cache
invalidation, incremental update, and monorepo scale are its own design.

**Non-blocking:** EI depends only on the *read-only Repository Understanding seam* (`10`), which is
fixed. EI tolerates absent/partial understanding (`02`, `09`), so it can be built and tested against
a minimal Repository Understanding before the full subsystem exists.

---

# G3 — Operator Preference model

**Open:** How Preferences are represented, seeded, and evolved (a Knowledge type? a Memory-backed
profile? both?) is specified only at the seam (`02`, `13`).

**Deferred because:** it depends on the Memory subsystem (itself deferred by the Knowledge package)
and on the preference-learning loop maturing.

**Non-blocking:** EI consumes Preferences read-only and tolerates their absence (conservative
defaults). A first EI can ship with empty/hand-seeded preferences and gain personalization later
with no core change.

---

# G4 — The reasoning capability behind generation

**Open:** Which capability EI uses for heuristic generation (`12`) — a hosted LLM, a local model, a
rules-first hybrid — and how its output is bounded/validated before becoming a Strategy.

**Deferred because:** it is a provider choice, and EI is provider-independent by construction (`13`,
INV-32). The choice can change without touching EI's architecture.

**Non-blocking:** the determinism seam (`12`) holds for *any* generation capability: whatever
produces the facets, the emitted Strategy is recorded and replayed as data (INV-17).

---

# G5 — Re-strategizing triggers and bounds

**Open:** The precise triggers that cause a mid-flight re-strategize (`04`, `12`) — which recovery
escalations, which discoveries — and the bound on how many times a goal may be re-strategized.

**Deferred because:** it couples to Recovery's escalation taxonomy (`../19`) and should be co-
designed with it.

**Non-blocking:** the *mechanism* (supersede-by-reference, recorded, bounded — `04`) is fixed;
only the *policy* of when to fire is open, and unfired re-strategizing degrades to today's behavior
(one Strategy per goal).

---

# G6 — Coherence rule calibration

**Open:** The exact functions binding autonomy ≤ f(risk) and rigor ≥ g(risk) (`04`, `08`, `09`) are
specified directionally, not numerically.

**Deferred because:** calibration needs real operational data (which risk levels warrant which
gates) and is itself a candidate for Knowledge-driven learning (`13`).

**Non-blocking:** the *directions* and *hard constraints* (higher risk → less autonomy, more rigor;
out-of-envelope → gate) are fixed and sufficient to build a safe, conservative first version.

---

# G7 — Interaction with Execution Strategy formalization

**Open:** The exact handoff between EI's *Coordination Intent* facet and the Execution Strategy
layer's *formalization* (`../13`) — how much EI expresses vs. how much that layer derives.

**Deferred because:** it is a seam-refinement between two declarative layers; both are additive and
can be reconciled during Execution Strategy's own next revision.

**Non-blocking:** EI expresses intent; the Execution Strategy layer already owns formalization
(INV-05). Worst case, EI's Coordination Intent is thin and the existing layer does more — no
invariant is at risk.

---

# G8 — Multi-goal / portfolio strategy

**Open:** EI as specified strategizes one Goal at a time. Cross-goal engineering strategy
(sequencing several related goals, sharing context, portfolio-level risk) is not modeled.

**Deferred because:** it is a Stage-4 ("Operational Ecosystem", `../00_VISION.md`) concern and
depends on multi-goal orchestration that does not yet exist.

**Non-blocking:** single-goal strategy is the correct first scope and composes upward later; nothing
here forecloses a portfolio layer above EI.

---

# G9 — Personal Workflow Model depth

**Open:** How deep "understands how I engineer" goes — commit style, review habits, architectural
preferences, per-repository practices — and how EI applies each without overfitting.

**Deferred because:** it is the richest form of G3 and needs the preference-learning loop plus
guardrails against over-personalization (a preference must never breach policy, `02`, `08`).

**Non-blocking:** the ceiling rule (preferences bias within policy, never beyond it) is fixed; depth
can grow behind that invariant.

---

# G10 — Human-interaction surface for clarification & approval

**Open:** EI proposes autonomy gates and can surface uncertainty, but the *channel* through which a
human approves a gate or answers a clarification is not EI's and is not yet built.

**Deferred because:** it is a platform-wide Human-Interaction subsystem (named in the operational
gap analysis) shared by Intent Resolution, Governance, and Recovery — not EI-specific.

**Non-blocking:** EI only *marks* where approval/clarification is required (`08`); enacting the
interaction is Governance's/Orchestration's, behind whatever channel the platform later provides.

---

# What is NOT a gap

For clarity, these are **settled**, not deferred:

- EI's placement (between Intent Resolution and Context Engineering) — settled (`00`).
- Repository Intelligence is a separate subsystem — settled (`10`).
- Intent Understanding stays in Intent Resolution — settled (`11`).
- The determinism seam (heuristic generation, recorded output, deterministic replay) — settled
  (`12`, `13`).
- Provider independence is permanent and structural — settled (`13`).
- EI is stateless and never self-updates — settled (`13`).

---

# North Star

Every frontier is named, and none of them reopens the core.

Engineering Intelligence can be built now against the fixed seams; each deferred item is an
extension the core already anticipates.
