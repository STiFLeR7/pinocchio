# Knowledge Observability

Status: Target Architecture (design only)

---

# Purpose

This document freezes what the Knowledge Engine makes observable. Observability here is
**instrumentation only** (doc 16 pattern): derived counters and distributions over the authoritative
`knowledge.*` event stream. It builds no dashboards, stores nothing durably, and **never influences
a Knowledge decision** — acceptance, evolution, and expiration remain pure functions of evidence and
policy.

---

# The authoritative record vs. derived metrics

The authoritative record of Knowledge is the `knowledge.*` event log and the Item projections
(`07`). Metrics are a *derived convenience* computed from that record. Every metric below can be
recomputed by replaying the log — none is a source of truth, and none feeds back into a decision.

---

# Required metrics

| Metric | Definition | Derived from |
|---|---|---|
| **Acceptance rate** | accepted candidates ÷ received candidates | `candidate_received` / `candidate_accepted` |
| **Rejection rate** | rejected candidates ÷ received candidates | `candidate_received` / `candidate_rejected` |
| **Evolution rate** | `item_evolved` events ÷ active Items (per window) | `item_evolved`, item projections |
| **Expiration rate** | `item_expired` (+`deprecated`) ÷ active Items (per window) | `item_expired` / `item_deprecated` |
| **Confidence distribution** | count of Active Items per confidence level (Experimental…Proven) | item projections |

These are the metrics the program requires. All are simple, deterministic aggregations — the same
event history yields the same metrics.

---

# Supporting signals (derived, optional)

- **Rejection reasons** — a breakdown of `candidate_rejected` by failed requirement (which policy
  threshold blocks most candidates) — feeds policy tuning by the owner (`08`), never automatic
  change.
- **Duplicate/merge ratio** — how often ingestion merges vs. creates (subject reuse).
- **Supersession count** — how often understanding is replaced (churn of a subject).
- **Serving distribution** — from sampled `knowledge.item_served` events (`07`): which subjects/kinds
  Planning and Context consume most (consumption observability).
- **Provenance depth** — average evidence references backing Active Items (a health signal for
  INV-24 grounding).

---

# Counters over the Phase-2 sink

Following the runtime/validation/recovery/reflection observability facades, Knowledge increments
named counters and records observations on the injected Phase-2 observability sink
(`knowledge.candidate_received`, `knowledge.candidate_accepted`, `knowledge.candidate_rejected`,
`knowledge.item_created`, `knowledge.item_evolved`, `knowledge.item_expired`, and a
`knowledge.confidence.<level>` gauge). The sink is instrumentation only; a `Null` sink is the
zero-overhead default. Counters never gate a decision.

---

# Explainability surface

Because every decision records its rationale, policy version, and evidence (`05`/`08`),
observability can expose *why* the aggregate looks as it does — e.g. a low acceptance rate resolves
to specific failed requirements, not an opaque score. This keeps operational tuning grounded in the
same auditable record as the decisions themselves.

---

# Boundary

Observability **describes** Knowledge; it never **decides** for it. No metric, rate, or distribution
is read by the Acceptance Engine, the evolution rules, or the expiration rules. Removing all
observability would change *visibility*, never *behaviour* or *outcomes*.

---

# North Star

Knowledge is fully legible: how much understanding it accepts, rejects, evolves, and retires, and
how confident that understanding is — all derived from the same immutable record that produced it,
and all incapable of steering it.
