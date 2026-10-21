# Nexus Operator Experience — Lessons Learned

## Architectural assumptions confirmed

- **An operator product is pure composition.** The interface that turns Nexus from an engineering
  platform into a usable operations product needed *no* new engine, contract, ADR, or invariant.
  `nexus_operator` is 317 statements of consumer code over the existing pipeline: submit drives the
  existing coordinators, and every read is a projection of persisted state. The whole value is the
  coherence, and every part already existed.
- **One object hides ten engines.** An operator submits a Goal and then monitors, inspects, searches,
  and aggregates through a single `OperatorSession` — never naming Context, Planning, Validation,
  Recovery, Reflection, or Knowledge. The success criterion (operate the control plane without
  knowing the engines) is met because the platform's public APIs were already complete enough to
  compose behind one facade.
- **Read models fall out of the event-sourced design for free.** Because state is persisted and
  every `WorkflowRun` retains its references and decisions, the timeline, explorers, search, and
  dashboard are all pure projections. No new persistence, no separate bookkeeping, no cache to
  invalidate — the dashboard is recomputed from the log on every access and is therefore always
  consistent with the truth.
- **Determinism carries all the way to the operator surface.** Two sessions running the same
  submission produce byte-identical event logs; search over the same state returns identical hits in
  identical order; replay reconstructs the log exactly. The operator sees a reproducible system, not
  a best-effort dashboard.

## Engineering refinements (all at the consumer boundary)

- **Correlate by node, never by index — again.** As with the Briefings composer, the explorer and
  dashboard must attribute validation/recovery decisions to the right work package, and the stages
  run in session order rather than declared order. Centralising the per-node correlation in one
  internal `analysis` helper kept the explorer and dashboard correct and free of duplicated
  index-alignment logic.
- **Report honest zeros.** `running_workflows` is always `0` because execution is synchronous. Rather
  than fake a concurrency model, the dashboard states the zero and documents why — a truthful metric
  beats an impressive-looking but meaningless one, and the field already has a clear meaning for a
  future async submission path.
- **Search is substring, deterministic, and repository-backed.** The mission forbids vectors and
  embeddings; a case-insensitive substring match over stable text fields, ordered by (domain, id),
  is fully deterministic and reuses the existing repositories and explorer views. Knowledge search
  reads the durable `KnowledgeRepository` directly, so it searches real accumulated understanding.
- **Thread Knowledge, don't rebuild it.** Carrying the durable Knowledge repositories from one
  submission to the next makes Knowledge grow across a session and lets a later submission's Planning
  consume earlier learning (INV-26) — the operator experiences the platform *getting smarter* within
  a session, with no operator-visible machinery.

## Architecture verification

- **No engine redesign** — `nexus_operator` calls existing entry points only; no engine package
  changed.
- **No contract changes** — every exchanged object is an existing `nexus_core` / engine / product
  value; the views, timeline, history, and dashboard are pure projections by reference (INV-27).
- **No ADR / invariant changes** — `docs/v2` ADRs and `99_ARCHITECTURAL_INVARIANTS.md` are
  untouched; the experience preserves ADR-001 (event-sourced), INV-04 (a package never plans),
  INV-20 (evidence-backed completion), INV-26 (Planning ← Knowledge only), INV-27 (reference-only).

## Future extension points

- **Interactive front-end** — the session, timeline, explorers, search, and dashboard are plain
  data structures; a CLI, TUI, or web UI is a thin rendering layer over them, adding no control-plane
  logic.
- **Asynchronous submission** — a background submission path would give `running_workflows` a
  non-zero meaning; every other dashboard field and every explorer view is already computed from
  persisted state and would not change.
- **Cross-session persistence** — today a session's history is in-memory; persisting submission
  records (they already reference everything by id) would let the explorer and dashboard span
  sessions without any new projection logic.
