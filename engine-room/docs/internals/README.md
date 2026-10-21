# `docs/internals/` — Code-Level Tours

Unlike `docs/v2/` (design intent, written before implementation) or `docs/runtime/` (per-subsystem,
as-built engineering notes), this directory holds cross-cutting tours of the actual v2 *codebase* —
answering "given the source tree, where do I start reading, and how does a request move through it?"

- [**WALKTHROUGH-v2.md**](WALKTHROUGH-v2.md) — the entry point, the composition-root pattern every
  package follows, the package map, the Spine's nine-stage pipeline, durable event sourcing, a worked
  example of how a Goal's identity flows through the system (and the RC2 defect class that taught that
  lesson), and how the test suite mirrors the package tree.

See [`docs/architecture/README.md`](../architecture/README.md) if you want the architecture portal
(design docs, ADRs, per-subsystem references) instead of a code tour.
