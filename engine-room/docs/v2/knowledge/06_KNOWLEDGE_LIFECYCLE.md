# Knowledge Lifecycle

Status: Target Architecture (design only)

---

# Purpose

This document freezes the canonical lifecycle of Knowledge — the states a unit passes through from
a proposed Candidate to Archived understanding, and the deterministic rules that govern each
transition. Every state change is an event (ADR-001); the current state is a projection.

---

# States

```
                 reject
Candidate ─────────────────▶ Rejected            (terminal for the candidate)
    │ accept
    ▼
Accepted ──▶ Active ──▶ Superseded ──▶ Archived
                │            ▲
                │ deprecate  │ supersede
                ▼            │
             Deprecated ─────┘
                │ expire
                ▼
              Expired ──▶ Archived
```

| State | Meaning |
|---|---|
| **Candidate** | proposed by Reflection; not yet judged (lives in Reflection's output, `02`) |
| **Rejected** | the Acceptance Engine declined it under policy (`05`); no Item exists/changes |
| **Accepted** | the Acceptance Engine approved it; an Item exists but is not yet in service |
| **Active** | the Item is current and **served to consumers** (`09`) |
| **Superseded** | a newer Item (different subject/version) replaces it; retained for provenance |
| **Deprecated** | still true historically but no longer recommended; withheld from default serving |
| **Expired** | staleness/TTL/evidence-obsolescence removed it from service (`11`) |
| **Archived** | retained immutably for audit/history; never served to consumers |

`Candidate` and `Rejected` belong to the ingestion boundary; `Accepted … Archived` are Item
lifecycle states.

---

# Transition rules (deterministic)

| From → To | Trigger | Rule |
|---|---|---|
| Candidate → Rejected | acceptance fails policy | records the failed requirement (INV-31); no Item mutated |
| Candidate → Accepted | acceptance passes policy | creates the Item (or the first version) via the Acceptance Engine (`05`) |
| Accepted → Active | admission to service | occurs once the Item meets the serving threshold (confidence/freshness, `09`) |
| Active → Active | evolution / merge | a new version accumulates evidence/confidence (`10`); state unchanged, version advances |
| Active → Superseded | a superseding Item is accepted | the superseding relationship is recorded on both Items (`03`) |
| Active → Deprecated | contradicting validated evidence, or policy deprecation | withheld from default serving; provenance retained |
| Deprecated → Superseded | a replacement Item is accepted | as Active → Superseded |
| Active/Deprecated/Superseded → Expired | freshness rule fires (`11`) | removed from service; deterministic, evidence-driven |
| Superseded/Expired/Deprecated → Archived | retention/compaction | immutable retention; never served |

All transitions are **deterministic functions** of the item's evidence, its relationships, and the
policy — no clock-driven guesswork (a TTL uses recorded timestamps as *data*, INV-17, evaluated
deterministically at query/maintenance time). No transition rewrites history; each is a new event.

---

# Serving and lifecycle

Only **Active** Items are served by default (`09`). `Deprecated`, `Superseded`, `Expired`, and
`Archived` are excluded from default retrieval but remain queryable for audit and provenance, and
remain part of the operational graph. This guarantees consumers (Planning/Context) prefer *current*
understanding (`../10_KNOWLEDGE.md` freshness) while nothing is ever lost.

---

# Reversibility & provenance

Because every state and version is an appended event, the lifecycle is fully **auditable and
reconstructable**: one can replay how an Item became Active, evolved, was superseded, and was
archived. No state is destructive; "removal from service" is a state, not a delete.

---

# North Star

Knowledge has a single, canonical life: proposed, judged, served, evolved, retired — every step on
the record. Understanding is preferred while current, retained while historical, and never silently
forgotten.
