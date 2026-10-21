# Knowledge Evolution

Status: Target Architecture (design only)

---

# Purpose

This document freezes how durable Knowledge **improves over time without losing provenance**:
versioning, superseding, merging, confidence evolution, and evidence accumulation. Evolution is the
reason Knowledge is *mutable through controlled change* while Candidates are immutable — it is
always additive, always auditable, never destructive.

---

# Versioning

Every accepted change to an Item's understanding creates a **new immutable version** (`03`):
`{subject_key, version, statement, confidence, provenance_added, policy_version, rationale,
timestamp}`. The current Item is the projection of the latest version; the version chain is the
item's full history. Versions are never rewritten or deleted. Version ids are deterministic
(`(subject_key, ordinal)`), so replay reproduces the exact chain.

---

# Evidence accumulation

When a new Candidate corroborates an existing Item (same Subject Key, new independent evidence), its
`evidence_refs` are **accumulated** into the Item's provenance. Accumulation is:

- **Additive** — evidence is added, never replaced or dropped;
- **Deduplicated by reference id** — the same evidence counted once (INV-16);
- **Reference-only** — evidence is held by id, never duplicated (INV-27).

Accumulated evidence is the substrate for confidence evolution.

---

# Confidence evolution

Confidence advances **deterministically** along the doc-26 ladder (Experimental → Observed →
Validated → Proven) as independent corroboration accumulates, under the policy's
`confidence_promotion` rule (`04`):

- more independent, validated evidence for the *same* understanding → promotion toward Proven;
- confidence is a pure function of the accumulated corroboration count/quality — **never learned,
  never AI-scored** (consistent with Reflection's deterministic confidence and `../10_KNOWLEDGE.md`);
- promotion is itself a versioned event (`knowledge.item_evolved`), so *how* an Item became Proven
  is on the record.

Contradicting validated evidence does not silently lower a number — it drives a **deprecation** or
**supersession** decision (`06`/`11`), preserving both the old and new understanding.

---

# Merging

When a Candidate matches a known subject but adds no new statement (only corroboration), the Engine
**merges** rather than creating a divergent version: evidence accumulates and confidence may
promote, but the statement is unchanged (`05`). Merging keeps one authoritative Item per subject
rather than scattering near-duplicates — the deterministic Subject Key (`03`) is what makes this
safe and reproducible.

---

# Superseding

When new understanding **replaces** older understanding (a better strategy, a corrected lesson), the
newer Item **supersedes** the older:

- the supersession relationship is recorded on **both** Items (`supersedes` / `superseded_by`, `03`);
- the superseded Item transitions to `Superseded` (`06`) and is withheld from default serving but
  retained for provenance;
- the new Item carries forward a reference to what it replaced — the lineage is never broken.

Superseding differs from evolution: evolution refines *one* subject's Item in place (new version);
superseding links *two* Items where one replaces the other.

---

# Provenance preservation (the invariant of evolution)

Across versioning, merging, and superseding, **provenance only grows**. Every version names the
candidates, patterns, evidence, and validated outcomes behind it; superseded Items retain their
full history; nothing that justified past understanding is ever discarded. This is what lets
Knowledge "improve over time without losing provenance," and it is the structural backing of INV-24.

---

# Determinism

Evolution is a pure function of `(incoming candidate, current Item + version chain, policy)`. The
same sequence of candidates always yields the same version chain, the same confidence trajectory,
and the same supersession graph — Knowledge is replayable end to end.

---

# North Star

Understanding compounds. The same lesson learned again strengthens one Item rather than fragmenting;
a better lesson supersedes the old without erasing it; and every step of that growth is a recorded,
reversible, evidence-backed version. Knowledge gets better — and never forgets how it got there.
