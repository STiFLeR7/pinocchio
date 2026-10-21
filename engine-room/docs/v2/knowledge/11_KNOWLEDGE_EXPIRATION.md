# Knowledge Expiration

Status: Target Architecture (design only)

---

# Purpose

This document freezes how Knowledge **remains current**: how freshness is tracked, and how obsolete
understanding is deprecated, expired, and archived — deterministically, and without ever destroying
provenance. Expiration is the counterweight to evolution: it keeps served Knowledge trustworthy by
retiring what no longer holds.

---

# Freshness states

Aligned with `../10_KNOWLEDGE.md` freshness, projected onto the lifecycle (`06`):

| Freshness | Meaning | Served by default? |
|---|---|---|
| **Current** | active, up-to-date understanding | yes (`Active`) |
| **Historical** | true but aged; kept for context/audit | no (queryable) |
| **Deprecated** | no longer recommended, though once valid | no |
| **Superseded** | replaced by a newer Item | no |
| **Archived** | retained immutably for the record | no |

Only **Current/Active** Knowledge is served by default (`09`); the rest remains queryable for audit
and provenance but is excluded from the understanding that steers new work.

---

# What drives expiration (deterministic triggers)

Expiration is never a guess. It fires from evidence and recorded data, evaluated deterministically:

1. **Supersession** — a newer Item replaces this one (`10`) → `Superseded`.
2. **Contradiction** — validated evidence contradicts the understanding → `Deprecated`, then a
   corrected/superseding Item may replace it.
3. **Staleness (TTL)** — the Item's recorded age exceeds a policy freshness window. Timestamps are
   **data** (INV-17); the TTL is evaluated deterministically at maintenance/query time, not by a
   background clock making non-reproducible decisions.
4. **Evidence obsolescence** — the artifacts/outcomes the Item references are themselves archived or
   invalidated → the Item's support has decayed → `Deprecated`/`Expired`.

Each trigger is a rule with a recorded rationale (INV-31) and emits the corresponding
`knowledge.item_deprecated` / `knowledge.item_expired` event (`07`).

---

# Expiration is a state, not a delete

Expiring Knowledge **removes it from service, never from history**:

- an `Expired` Item stops being served but remains an immutable part of the event stream and the
  operational graph;
- `Archived` is the terminal retention state — retained for audit, never served;
- provenance is preserved through every step (`08`/`10`); an expired lesson can still explain a past
  decision that relied on it.

There is no destructive deletion in the Knowledge architecture. "Forgetting" is a lifecycle state,
so the platform can always answer *what did we believe then, and why did it retire?*

---

# Reactivation

Expiration by staleness is **not** a permanent verdict on a subject. If a later, stronger Candidate
for the same Subject Key clears policy (`04`/`05`), it creates a fresh version/Item that becomes
`Active` — the subject returns to service on new evidence, with the expired history retained as
provenance. (Deprecation by contradiction, by contrast, requires the contradiction itself to be
resolved by a superseding Item.)

---

# Determinism & maintenance

A dedicated, deterministic maintenance pass evaluates freshness rules over the store and applies the
resulting transitions — a pure function of `(Items, recorded timestamps, referenced-artifact state,
policy)`. Running the pass twice on the same state yields the same transitions. No expiration
depends on wall-clock timing of when the pass happens to run; it depends only on recorded data.

---

# North Star

Served Knowledge is current Knowledge. Understanding that no longer holds steps out of the way of
new work — quietly retired, fully retained, and ready to be relearned on stronger evidence.
