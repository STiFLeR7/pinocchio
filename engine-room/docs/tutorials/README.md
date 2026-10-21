# Nexus v2 Tutorials

Ten guided tutorials, each teaching one concept and building on the last. Where
[`examples/`](../../examples/) shows *what* the platform does through runnable code, tutorials explain
*why* it works that way and how to reason about it — then send you to the example to run it yourself.
**No tutorial duplicates an example's code.** Each one references the relevant `examples/NN-*/run.py`
directly; read the code there, don't expect it re-pasted here.

## Prerequisites

Same as the example library: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), run from the repository
root. See [`docs/getting-started/README.md`](../getting-started/README.md) if you haven't installed
anything yet — start there, not here.

## Learning Path

| # | Tutorial | Teaches | Builds on | Uses example |
|---|---|---|---|---|
| [01](01-installing-nexus.md) | Installing Nexus | Environment setup, verifying the install, the v1/v2 split | — | — |
| [02](02-first-pipeline.md) | Running Your First Pipeline | Goal → Knowledge, the smallest possible run | 01 | [01](../../examples/01-hello-nexus/) |
| [03](03-constitutional-pipeline.md) | Understanding the Constitutional Pipeline | All nine stages, why they're fixed-order, the Operations plane | 02 | [02](../../examples/02-first-pipeline/) |
| [04](04-memory.md) | Working with Memory | Durable Knowledge items, reading them back by identity | 03 | [05](../../examples/05-memory/) |
| [05](05-scheduling-work.md) | Scheduling Work | `tick()`, one-time vs. recurring dispatch, restart | 03 | [06](../../examples/06-scheduler/) |
| [06](06-approval-exchange.md) | Approval Exchange | Gated nodes, the human-in-the-loop pause/resume lifecycle | 03 | [07](../../examples/07-approval-exchange/) |
| [07](07-replay-and-recovery.md) | Replay & Recovery | Exact reconstruction from the log; deterministic recovery from failure | 05 | [08](../../examples/08-replay/), [09](../../examples/09-recovery/) |
| [08](08-runtime-adapters.md) | Runtime Adapters | The `RuntimeAdapter` protocol, swapping runtimes without touching the pipeline | 03 | [04](../../examples/04-runtime-selection/) |
| [09](09-policy-authoring.md) | Policy Authoring | Writing a `DecisionRequest`/policy, fail-closed by default, precedence order | 03 | [03](../../examples/03-policy-governance/) |
| [10](10-autonomous-workflow.md) | Building Your First Autonomous Workflow | Composing everything above into one no-human-in-the-loop goal | 04, 05, 06, 07, 08, 09 | [10](../../examples/10-autonomous-workflow/) |

## Why this order

01–03 are the only tutorials every reader needs, in order — everything after 03 branches out from the
same base (a working pipeline) into one capability each, and 08/09 (Runtime Adapters, Policy Authoring)
can be read in either order or skipped independently since neither depends on the other. 10 is the
capstone: it doesn't teach a new concept, it composes 04–09's mechanisms into the same "Daily Research
Agent"-shaped showcase [`examples/10-autonomous-workflow/`](../../examples/10-autonomous-workflow/)
demonstrates.

## What these tutorials are not

They are not a restatement of [`docs/architecture/README.md`](../architecture/README.md) (the full
design reference) or [`docs/internals/WALKTHROUGH-v2.md`](../internals/WALKTHROUGH-v2.md) (the code-level
tour). Tutorials are the shortest path to *doing* something correctly; when you want the full design
rationale behind what you just ran, each tutorial's "Go deeper" line points at the relevant design doc.

## After the tutorials

[`docs/development/CONTRIBUTING.md`](../development/CONTRIBUTING.md) — turn what you've learned into a
pull request.
