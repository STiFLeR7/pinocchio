# Nexus Briefings — Lessons Learned

## Architectural assumptions confirmed

- **A user-facing product is pure composition.** The first product built *on* the platform — the
  Briefings system — needed *no* new engine, contract, ADR, or invariant. `nexus_briefings` is 234
  statements of consumer code over the existing pipeline. The transition from "building the
  platform" to "delivering value through it" cost zero foundational change; the value is the
  composition, and every part already existed.
- **A briefing is a governed workflow, not a report script.** Instead of querying state and
  formatting it (the v1 approach), a briefing is *planned, executed, validated, recovered,
  reflected on, and learned from* by the real engines. The product inherits the platform's
  governance for free: an unvalidated section cannot be published, and every generation is a
  replayable, deterministic operation.
- **Configuration, not code, is the extension point.** Four products — Operational Digest, Research
  Brief, Architecture Brief, Project Brief — are the same code path over four `BriefType` values.
  Planning decomposes whatever sections a type declares; the composer projects whatever ran; the
  renderers format whatever was composed. A fifth product is a new value, not a new workflow.
- **Provider-independence carries through to the product.** Because briefings drive the pipeline
  through Capability Program 2's adapter seam, the same briefing generates on Claude, Gemini, or
  Shell with identical governance and only runtime-specific artifacts differing — without a line of
  runtime-aware code in `nexus_briefings`.
- **The learning loop is generic.** Every generated briefing is itself an observable operation:
  Reflection analyzes it and Knowledge persists reusable insight, so a second generation's Planning
  improves through Knowledge consumption alone (INV-26) — and the learning even crosses a runtime
  switch, because Knowledge is about the subject, not the provider.

## Engineering refinements (all at the consumer boundary)

- **"Never consume raw runtime output" is enforced, not documented.** The composer both excludes the
  runtime's captured-output stream and gates every deliverable on the Validation verdict. The test
  suite proves a failed generation withholds *all* artifacts even though the runtime produced files,
  and that no composed artifact carries the raw-output marker.
- **Correlate by node, never by index.** Execution / validation / recovery stages run in session
  order, which is *not* the declared section order. Keying composition on the node id (and reading
  each decision at the aligned index) is the difference between a correct brief and one whose
  sections silently swap. A declared section with no matching node is withheld as `absent`, never
  fabricated from a fallback.
- **Determinism reaches the delivered artifact.** Renderers take no clock and no environment, so a
  brief is byte-identical across runs — the v1 renderer's `datetime.now()` would have broken replay
  parity. Product surfaces get the same determinism guarantee the control plane has.
- **Reuse the aesthetic, not the coupling.** The v1 renderer is bound to the v1 database and a live
  clock; importing it would violate v2 layering. The v2 renderers reuse its look (status line,
  per-section blocks, findings, footer) as dependency-free projections of the governed `Brief`.

## Architecture verification

- **No engine redesign** — `nexus_briefings` calls existing entry points only; no engine package
  changed.
- **No contract changes** — every exchanged object is an existing `nexus_core` / engine value; the
  `Brief` and `BriefingSession` are pure projections by reference (INV-27).
- **No ADR / invariant changes** — `docs/v2` ADRs and `99_ARCHITECTURAL_INVARIANTS.md` are
  untouched; the product preserves ADR-001 (event-sourced), INV-04 (a package never plans), INV-20
  (evidence-backed completion), INV-26 (Planning ← Knowledge only), INV-27 (reference-only).

## Future extension points

- **Delivery channels** — the renderers produce Markdown / HTML / JSON strings; wiring them to a
  delivery surface (chat, email, webhook) is a channel concern outside the control plane, and the
  `is_publishable` gate is the sanctioned check before sending.
- **Scheduled generation** — a scheduler invoking `generate()` on a cadence turns the deterministic
  briefing into a recurring operational product; each run is independently replayable.
- **Research-backed briefings** — the workflow's optional Research step (a `research-brief` type
  already reuses the research phases) can precede composition for briefings that gather sources
  before summarizing, all within one governed pipeline.
