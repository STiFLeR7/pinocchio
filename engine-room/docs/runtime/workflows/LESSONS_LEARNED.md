# End-to-End Workflow -- Lessons Learned

## Architectural assumptions confirmed

- **The ten engines compose with zero redesign.** Every engine's real entry point accepted the
  previous engine's real output (or a pure by-value projection of it). No engine, contract, ADR, or
  invariant was touched; the integration is 275 statements of wiring over existing APIs. The
  control plane genuinely functions as one coherent system.
- **The dependency discipline paid off end-to-end.** Each engine imports only downward, so the
  whole chain is acyclic and `nexus_workflows` -- the one layer allowed to import everything -- sits
  cleanly on top, imported by nothing (guardrail-tested).
- **One shared substrate is enough.** A single `build_infrastructure()` + one injected
  `TimestampSource` gave every engine one authoritative log and one deterministic clock, making the
  entire multi-engine run replayable and byte-identical across executions with no extra machinery.
- **INV-26 holds through a real pipeline.** Planning takes no Knowledge/Reflection parameter; the
  coordinator reads Knowledge and folds it into the `PlanningRequest`, so learning influences
  Planning strictly through a read-only query. The invariant survived contact with an actual run.

## Engineering refinements (all at the integration boundary, no engine change)

- **The Harness->Runtime seam is the only hand-written hop.** Runtime is deliberately isolated from
  upstream types, so `project_intake` maps a compiled `ExecutionPackage` (paired with its
  `RuntimeRequest` and `ExecutionManifest` by node) into the `nexus_core`-only `RuntimeIntake`.
  Every other hop is a direct type handoff. This confirmed the runtime-isolation design: the seam
  is small, explicit, and reference-only.
- **Orchestration produces runtime candidates from its harness registry.** The runtime must be
  registered in *two* places -- the Orchestration harness registry (so it is offered as a
  candidate, INV-37) and the Runtime registry (for selection). Missing the first yields "no
  candidate runtimes"; missing the second yields "no eligible runtime". Both are registrations, not
  redesigns.
- **Runtime capacity is a workflow configuration.** Default runtime capacity is 1; a workflow with N
  ready nodes registers the runtime descriptor with `capacity = N` (metadata) so a batch prepare
  does not exhaust it. This is a deployment/config value the integration boundary owns, not a
  contract change.
- **Two independent work items make the learning loop observable.** Reflection only proposes a
  Knowledge Candidate from a *confirmed* pattern (>= 2 episodes), so the reference workflow
  decomposes into two independent nodes -- enough to confirm a `REPEATED_SUCCESS` (or, on the
  failure path, `REPEATED_FAILURE`) and feed Knowledge.
- **A spike before the package saved debugging.** Proving the full live chain in a throwaway script
  first surfaced all four real handoff mismatches (unregistered strategy, `manifest_ref` type,
  capacity, candidate registration) before any package code existed -- systematic evidence at each
  boundary rather than guesswork.

## Architecture verification

- **No engine redesign** -- `nexus_workflows` calls existing entry points only; the diff touches no
  engine package.
- **No contract changes** -- every object exchanged is an existing `nexus_core` / engine value
  object; only registration bookkeeping and two pure by-value projections were added.
- **No ADR changes / no invariant changes** -- `docs/v2` ADRs and `99_ARCHITECTURAL_INVARIANTS.md`
  are untouched; the run preserves ADR-001 (event-sourced), INV-16/17 (deterministic), INV-26
  (Planning<-Knowledge only), INV-27 (reference-only), INV-37 (candidates only).

## Future extension points

- **Multi-runtime / heterogeneous selection** -- register several runtime descriptors; orchestration
  already offers candidates and the Runtime selector chooses deterministically.
- **Dependent work graphs** -- the reference workflow uses independent nodes; a dependency edge
  makes orchestration release ready nodes in waves, which the coordinator can drive iteratively.
- **Recovery-driven re-execution** -- today a RETRY decision is recorded and reflected; a future
  coordinator loop could re-prepare a new attempt from the Recovery Plan (the `attempt` field on the
  intake already exists) without any engine change.
- **Live runtimes** -- the same flow runs against a real Claude CLI by swapping the stub invoker
  (the `NEXUS_CLAUDE_SMOKE` opt-in path), with no pipeline change.
