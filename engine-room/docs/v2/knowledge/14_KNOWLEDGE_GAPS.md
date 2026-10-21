# Knowledge Gaps

Status: Target Architecture (design only)

---

# Purpose

This document records the **open questions and deliberately deferred decisions** in the Knowledge
architecture. Everything here is *out of scope* for the first implementation and must be resolved by
a future design pass before it is built. Listing them explicitly is what lets the rest of the
architecture be frozen: an implementation team can build the defined core without waiting on these.

Each gap names the deferral so silence is never mistaken for coverage.

---

# G1 — Memory boundary

`../10_KNOWLEDGE.md` distinguishes **Memory** (stores information) from **Knowledge** (stores
understanding). Memory is a **separate future subsystem** and is out of scope here. The exact seam —
what Knowledge references *in* Memory vs. what it holds itself, and whether Memory becomes an
ingestion source — is deferred. The current architecture holds understanding by reference (INV-27)
and does not depend on Memory existing.

---

# G2 — External and non-Reflection ingestion

The frozen ingestion path is **Reflection-only** (candidates → acceptance). `../10_KNOWLEDGE.md`
lists other potential sources (documentation, research, operator decisions, external systems). How
those become policy-gated candidates — and how their provenance satisfies INV-24 without a
Validation Report — is deferred. The candidate contract (`02`) is shaped generically enough to admit
them later without redesign.

---

# G3 — Semantic operational graph

`../10_KNOWLEDGE.md` envisions a connected operational graph and semantic retrieval. This design
freezes *typed relationships and deterministic subject-key linkage* (`03`) but **not** semantic
similarity, embedding-based retrieval, or automatic relationship discovery. Those are deferred and
must remain deterministic-or-clearly-marked-non-deterministic when introduced.

---

# G4 — Automatic pattern discovery & cross-project learning

Reflection today discovers patterns within one operational window. Cross-window and cross-project
pattern mining, and organization-wide learning (`../10_KNOWLEDGE.md` Future Evolution), are
deferred. Knowledge's subject-key model (`03`) is the substrate that would make cross-window
accumulation deterministic when this is designed.

---

# G5 — Confidence model richness

Confidence is a deterministic, count-derived ladder (Experimental…Proven, `10`). Richer scoring —
weighting evidence quality, recency, or contradiction strength — is deferred. Any future model must
preserve determinism and explainability (no opaque/AI score), consistent with the platform.

---

# G6 — Conflict resolution beyond supersession

The model handles contradiction via deprecation/supersession (`06`/`11`). More nuanced conflict
handling — partial contradiction, context-scoped truth ("true for repo A, not repo B"), or
confidence-weighted coexistence — is deferred. Subject-key canonicalisation (`03`) is the natural
place such scoping would attach.

---

# G7 — Multi-tenant isolation & read authorization

Cross-tenant separation of Knowledge, per-consumer read authorization, and encryption-at-rest are
out of scope (`13`). The current design is correct for a single-operator, single-store deployment.
Multi-tenant Knowledge requires a dedicated security design.

---

# G8 — Retention, compaction & scale

Archival is defined as a state (`11`), but long-horizon retention policy, event-log compaction/
snapshotting for very large knowledge bases, and storage-tiering are deferred. The event-sourced
model (ADR-001) already supports snapshots; the *policy* for when to compact is unspecified here.

---

# G9 — Candidate-contract ownership

The candidate crosses the Reflection→Knowledge boundary **by value** (`02`), with Knowledge importing
no upstream layer. Whether the candidate shape should be promoted to a shared **`nexus_core`
contract** (so both producer and consumer reference one canonical type, ADR-003) versus adapted at
the ingestion boundary is a Phase-0 implementation choice, recorded in `ARCHITECTURE_REVIEW.md`.
Either option preserves the dependency direction; the architecture does not hinge on it.

---

# G10 — Research & Autonomous Workflows

Knowledge is designed to *feed* future Research and Autonomous Workflow subsystems, but their
consumption patterns (e.g. an autonomous loop that plans from Knowledge, acts, and reflects back)
are not yet specified. The read-only consumption contract (`09`) is intended to serve them
unchanged; confirming that is deferred to those subsystems' designs.

---

# Non-gaps (explicitly settled here)

To avoid re-litigation, these are **decided**, not gaps: dependency direction (`00`); the
candidate→acceptance→item→serve pipeline (`01`); deterministic subject-key identity (`03`);
policy-gated, evidence-required acceptance (`04`/`05`); the lifecycle states and transitions (`06`);
the `knowledge.*` event taxonomy (`07`); event-sourced, reference-only, read-only-to-consumers
integrity (`07`/`08`/`09`/`13`); deterministic evolution and expiration (`10`/`11`).

---

# North Star

The core is frozen; the frontier is named. Nothing in this list blocks building the defined
Knowledge Engine — and nothing in the defined Knowledge Engine pretends to have solved what this
list defers.
