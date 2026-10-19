# Knowledge Security

Status: Target Architecture (design only)

---

# Purpose

This document freezes the security posture of Knowledge: what it may hold, how it protects
integrity and provenance, how it stays read-only to consumers, and how it excludes secrets. Because
Knowledge influences *future* executions, its integrity is a security property — poisoned or
tampered understanding would misdirect Planning.

---

# Reference, never duplicate (INV-27)

Knowledge Items, versions, candidates, and events reference artifacts and evidence **by id and never
embed their content** (INV-27, ADR-003). This is both a modelling rule and a security rule:

- an Item cannot become a covert copy of source material, logs, or artifact bodies;
- referenced content stays behind its own access controls; Knowledge holds only pointers and small,
  deterministic descriptors;
- the same rule that keeps artifact bytes out of events keeps them out of Knowledge.

---

# Secret exclusion

No Knowledge object may contain a secret. Understanding is expressed as operational statements and
references — never credentials, tokens, keys, or raw environment values. This inherits the
platform's secret discipline (runtime doc 17): secrets live only in `.env`, reach runtimes by
injected reference, and are redacted from outputs/events — so they are never present in the Evidence
or Candidates Knowledge ingests, and must never be reconstructed into a statement. A candidate that
would require embedding a secret to be meaningful is rejected, not sanitised-and-stored.

---

# Integrity & tamper evidence

Knowledge is **event-sourced and append-only** (ADR-001): its state is a projection of an immutable
log with optimistic concurrency and idempotent, deduped application (INV-16). Consequently:

- history cannot be silently rewritten — an altered past would leave the log inconsistent;
- every version, supersession, and expiration is a recorded, ordered fact;
- rebuilding Knowledge from the log is deterministic, so divergence is detectable.

Integrity of understanding therefore rests on the integrity of the Phase-2 store, which Knowledge
reuses unchanged rather than inventing a weaker mechanism.

---

# Provenance integrity

Provenance is the anti-poisoning control. Acceptance requires that a candidate's evidence trace to
**validated** outcomes (INV-24, `05`), so understanding cannot be injected from unvalidated or
fabricated input. Provenance is preserved and only-grows across evolution (`10`), so the evidentiary
basis of any statement is always inspectable and cannot be quietly detached.

---

# Read-only to consumers

Consumers (Planning, Context, Orchestration) receive **immutable views by reference** (`09`) and
have no write path — no ability to inject, evolve, deprecate, or expire Knowledge. The Knowledge
Engine is the sole writer (`08`). This closes the obvious tampering vector: nothing downstream can
edit the understanding that steers it.

---

# Least authority & isolation

- Knowledge imports only `{nexus_core, nexus_infra}` (`00`); it has no execution, runtime, or
  network capability — it cannot be used as an execution or exfiltration vector.
- Ingestion is idempotent by candidate identity (INV-16), so replay or duplicate submission cannot
  amplify or corrupt state.
- Changing the Persistence Policy is a governed, owned, audited act (`04`/`08`) — the acceptance
  bar cannot be lowered anonymously.

---

# Threats explicitly out of scope (deferred to `14`)

Cross-tenant knowledge isolation, encryption-at-rest of the knowledge store, fine-grained read
authorization per consumer, and ingestion from *external* (non-Reflection) sources are **not** part
of this frozen scope; they are recorded as gaps (`14`) for a later security pass. The current
architecture is secure for the single-operator, Reflection-only ingestion path it defines.

---

# North Star

Knowledge is a trustworthy influence on future work precisely because it references rather than
copies, excludes secrets, records everything immutably, admits only evidence-backed understanding,
and can be written by no one but its own Engine.
