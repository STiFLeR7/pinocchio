# Multi-Agent Runtime Integration — Lessons Learned

## Architectural assumptions confirmed

- **The Runtime abstraction is genuinely provider-agnostic.** Two new runtimes — one model-backed
  (Gemini), one with a completely different vocabulary (Shell) — dropped in as pure
  implementations of the existing nine-concern `RuntimeAdapter` protocol. No engine, contract,
  ADR, or invariant changed. RM core and the Execution Engine still import no concrete adapter and
  branch on no provider (doc 03 §3 litmus holds with three providers, not one).
- **A different runtime is a normalization difference, nothing more.** A shell has no "tool use"
  or "progress" vocabulary, yet it drives the whole pipeline identically. The entire delta between
  Claude, Gemini, and Shell lives in each adapter's `_normalize` — everything downstream (events,
  governance, validation, recovery, reflection, knowledge) is byte-for-byte the same code.
- **Selection was already provider-independent.** Milestone 5 needed *no new algorithm*: the
  Runtime Manager's `RuntimeSelector` (`match → health → policy → choose`) already selects
  deterministically over abstract capabilities and declarative policy. `select_runtime` just
  projects the adapter registry into the `RUNTIME` Registry lens and reuses it — reuse over
  reinvention kept selection consistent by construction.
- **Governance is invariant to the runtime; artifacts are not.** Removing the three
  runtime-*variable* event types (`output` / `progress` / `artifact_emitted`) leaves a governance
  skeleton that is identical across all three runtimes. This is the precise, testable meaning of
  "identical governance; only runtime-specific artifacts may differ" (Milestone 6).

## Engineering refinements (all additive; no engine change)

- **One injected seam unlocked cross-runtime execution.** The `WorkflowCoordinator` hard-wired the
  Claude adapter. Adding an optional `adapter_factory` (defaulting to the exact Claude
  construction) made the workflow provider-agnostic while keeping every existing test — including
  the byte-identical determinism guarantees — green. The adapter is the *only* provider-specific
  choice in the pipeline, so it is the only thing the seam exposes.
- **The registry must name no provider; the catalog may.** Keeping `registry.py` / `selection.py`
  free of any `nexus_runtime_{claude,gemini,shell}` import (guardrail-tested) is what makes "add a
  runtime without architectural change" true. The concrete wiring lives in one composition module
  (`catalog.py`) — the same discipline every layer's in-memory reference registry follows.
- **A deterministic-run profile, not a test flag.** Threading `fail` / `hang` into the adapter
  factory as a `RuntimeInvocationProfile` (rather than an ad-hoc boolean) kept the registry general:
  it describes how a stub-backed runtime's event stream should behave for reproducible runs, which
  is a first-class property of every adapter in the codebase, not a test concern leaking in.
- **Capability advertising is the compatibility contract.** For the *same* Work Package to be
  eligible on all three runtimes, each had to advertise the capability the package requires
  (`code_generation`). Cross-runtime compatibility is therefore a capability-match fact the selector
  already enforces — not special-casing, and not a lowered requirement.

## Architecture verification

- **Runtime Manager unchanged** — `nexus_runtime` is untouched; selection *reuses* its
  `RuntimeSelector`.
- **Execution unchanged** — `nexus_execution` drives all three adapters through the same protocol.
- **Validation / Recovery / Reflection / Knowledge unchanged** — they consume runtime-independent
  results and never learn which provider ran.
- **No ADR / contract / invariant changes** — `docs/v2` ADRs and `99_ARCHITECTURAL_INVARIANTS.md`
  are untouched; the work preserves ADR-002 (single registry, `RUNTIME` lens), ADR-003/INV-27
  (reference-only), INV-16/17 (deterministic), INV-32 (provider-independent capability matching),
  INV-36 (Registry owns availability/health), INV-37 (candidates only, RM selects).

## Future extension points

- **Docker / Python-sandbox / Browser / MCP / Remote-Worker** — each is one more `RuntimeAdapter`
  implementation plus one `catalog` registration; the registry, selector, and every engine are
  ready for them today.
- **Heterogeneous batches** — register several runtimes as candidates and let `runtime_policy`
  route different Work Packages to different runtimes within one workflow; the selector already
  chooses per-intake.
- **Live runtimes** — swap each stub invoker for its real CLI/subprocess counterpart
  (`ClaudeCliInvoker` / `GeminiCliInvoker` / `SubprocessShellInvoker`) with no pipeline change; only
  determinism (not governance) relaxes.
