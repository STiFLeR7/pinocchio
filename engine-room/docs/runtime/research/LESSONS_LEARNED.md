# Autonomous Research Workflow — Lessons Learned

## Architectural assumptions confirmed

- **A production capability is pure composition.** An autonomous research workflow — arguably the
  headline use case — needed *no* new engine, contract, ADR, or invariant. `nexus_research` is 161
  statements of consumer code over the existing pipeline. The platform was designed for exactly
  this: the value is the composition, and every part already existed.
- **"Research" is not a special planner.** The four research phases (gather → summarize → compare →
  generate) are *declared* as Work Items; the existing Planning engine decomposes them into Work
  Packages and an Execution Graph. Verification asserts Planning produced one Work Package per
  phase — proving the decomposition is Planning's, not the research layer's (INV-04).
- **Research inherits provider-independence for free.** Because it drives the existing pipeline
  through Capability Program 2's adapter seam, the same research workflow runs on Claude, Gemini, or
  Shell with identical governance and only runtime-specific artifacts differing — without a line of
  runtime-aware code in `nexus_research`.
- **The learning loop is generic.** Knowledge feedback needed no research-specific machinery: the
  existing `nexus_workflows` loop, driven with a research topic and a shared Knowledge store, makes
  a second run's Planning consume the first run's Knowledge (never Reflection). Learning even
  crosses a runtime switch, because Knowledge is about the subject, not the provider.

## Engineering refinements (all at the consumer boundary)

- **The Research Brief is a projection, not an artifact.** Rather than invent a deliverable type,
  the brief reorganizes the existing `WorkflowRun` into research terms (sources, briefing, evidence,
  findings, knowledge) by reference only. Keeping produced deliverables (Execution stages) distinct
  from the evidence that judged them (Validation stages) avoided conflating a phase's output with
  its proof.
- **What-if recovery probes need isolated logs.** Demonstrating retry → escalate → resume from a
  single failure means calling the Recovery engine three times on the same session; those calls
  share deterministic event ids and collide on one log. Running each hypothetical on its own
  throwaway infrastructure kept the probe honest (real engine, real decisions) without polluting the
  research run's log — the same "isolate the what-if" discipline the Knowledge engine's ingest ids
  taught earlier.
- **Failure injection is an input change, never an engine change.** Retry is shown live via the
  failing runtime path; escalate/resume are shown by injecting an attempt count, a checkpoint, and a
  partial verdict into the *existing* engine. Every governed continuation is the platform's decision.
- **Independent phases make learning observable.** Four independent research phases give Reflection
  four episodes — enough to confirm a reusable pattern and feed Knowledge — mirroring why the
  end-to-end reference workflow uses independent nodes.

## Architecture verification

- **No engine redesign** — `nexus_research` calls existing entry points only; no engine package
  changed.
- **No contract changes** — every exchanged object is an existing `nexus_core` / engine value; the
  brief and session are pure projections.
- **No ADR / invariant changes** — `docs/v2` ADRs and `99_ARCHITECTURAL_INVARIANTS.md` are
  untouched; the workflow preserves ADR-001 (event-sourced), INV-04 (a package never plans),
  INV-20 (evidence-backed completion), INV-26 (Planning ← Knowledge only), INV-27 (reference-only).

## Future extension points

- **Dependent research graphs** — the phases run independently today; a `depends_on` edge
  (gather → summarize → compare → generate) would let Orchestration release them in waves, which a
  future coordinator loop can drive iteratively (the same extension the end-to-end workflow noted).
- **Real corpora** — swapping each stub invoker for its live CLI/subprocess turns the deterministic
  research run into a real one (gathering real sources, generating a real briefing) with no pipeline
  change; only determinism relaxes, not governance.
- **Heterogeneous stages** — a research policy could route `gather-sources` to the shell and
  `generate-briefing` to a model runtime within one workflow; the existing selector already chooses
  per stage.
