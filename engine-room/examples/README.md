# Nexus v2 — Examples

Ten runnable examples, each demonstrating exactly one architectural capability of the released
`v2.0.0` platform. Every example is real code against real, released APIs — nothing here is
pseudo-code, and nothing invents a capability the platform doesn't have. Every example was executed
directly before being committed; see `docs/DOCUMENTATION_PHASE4_REPORT.md` for the validation record.

## Prerequisites (all examples)

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) — see the repository root
  [`README.md`](../README.md#installation) for setup.
- Run from the repository root: `uv run python examples/01-hello-nexus/run.py` (or activate the
  `.venv` and run `python examples/01-hello-nexus/run.py` directly).
- No external services, API keys, or network access — every example uses the platform's own
  deterministic stub runtimes (the same ones the test suite uses) or an in-memory/temp-file durable
  log. Nothing here calls a real LLM.

## Learning Progression

Each example builds on a concept the previous one introduced. Read them in order the first time
through; come back to any one individually afterward.

| # | Example | Capability | Builds on |
|---|---|---|---|
| [01](01-hello-nexus/) | Hello Nexus | The smallest complete Goal → Completion run | — |
| [02](02-first-pipeline/) | First Pipeline | All nine constitutional stages, named, plus the Operations plane observing them | 01 |
| [03](03-policy-governance/) | Policy Governance | The Policy Engine standalone — fail-closed, explainable, precedence-ordered | 02 |
| [04](04-runtime-selection/) | Runtime Selection | Swapping the runtime adapter (Claude → Shell) without touching anything above it | 01 |
| [05](05-memory/) | Memory (Knowledge) | Reading back a durable Knowledge Item a run produced | 02 |
| [06](06-scheduler/) | Scheduler | One-time and recurring dispatch, then a real restart over the same durable file | 02 |
| [07](07-approval-exchange/) | Approval Exchange | A gated node pausing execution, then resuming on an operator's decision | 02 |
| [08](08-replay/) | Replay | Reconstructing state from the durable log alone, after discarding all in-memory objects | 06 |
| [09](09-recovery/) | Recovery | A failed execution still reaching a deterministic, governed, recorded outcome | 02 |
| [10](10-autonomous-workflow/) | Autonomous Workflow | The showcase — a Fully-Automatic goal that runs itself end to end, no human in the loop | 03, 06, 07, 09 |

## Why these ten, and not others

This set maps directly to the ten subsystems/capabilities most worth demonstrating standalone:
the core pipeline (01, 02), governance (03), pluggable execution (04), durable memory (05), timing
and autonomy (06, 10), the human-in-the-loop gate (07), and the two guarantees that most
differentiate Nexus from a simple agent framework (08 replay, 09 recovery). Every example composes
existing, tested composition roots (`build_constitutional_pipeline`, `build_policy`,
`build_scheduler`, `build_approval_exchange`, `build_operations`, `build_knowledge_repositories`) —
none of them required a new API, a new test fixture, or a change to any `nexus_*` package.

## If something doesn't run

See each example's own README "Troubleshooting" section first. Two things apply across all ten:

- **`ModuleNotFoundError: No module named 'nexus_...'`** — the v2 packages aren't installed into your
  environment. Run `uv sync` from the repository root first.
- **`UnicodeEncodeError` on Windows** — some platform strings (policy reasoning traces, in
  particular) include non-ASCII characters; every example already calls
  `sys.stdout.reconfigure(encoding="utf-8")` for this reason. If you've copied code out of an example
  into your own script, carry that line with it.
