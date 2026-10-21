# Getting Started with Nexus v2

**Target: a first successful run in under 15 minutes.** This page is the reader's actual first stop —
clone, install, run one example, understand the shape of the architecture, then continue into the
tutorials. If you already know you want the deep design reference instead of a quick start, go straight to
[`docs/architecture/README.md`](../architecture/README.md).

> **Working on Nexus v1** (`nexus/`, the Discord-fronted control plane) instead? This page is v2-only —
> start with [`ONBOARDING.md`](../../ONBOARDING.md) instead. Not sure which you need? See
> [`docs/README.md`](../README.md).

## The journey

```
clone → install → run first example → understand architecture → continue into tutorials
```

### 1. Clone (30 seconds)

```bash
git clone https://github.com/STiFLeR7/nexus.git
cd nexus
```

### 2. Install (1–2 minutes)

```bash
uv sync
```

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) — `uv` provisions the interpreter itself, so
you don't need Python pre-installed. No database, no API key, no config file. v2's entire third-party
runtime footprint is `pydantic`.

### 3. Run your first example (2 minutes)

```bash
uv run python examples/01-hello-nexus/run.py
```

You should see output ending in `status: completed`, `succeeded: True`, and a list of all nine
constitutional stage names. That's a full Goal → Knowledge run — the smallest possible one — completing
entirely locally, with no network access, against a deterministic stub runtime.

**If this didn't work**, see [Troubleshooting](#troubleshooting) below before continuing.

### 4. Understand the architecture (5 minutes)

Read the root [`README.md`](../../README.md)'s "What is Nexus?", "Core Capabilities", and "Architecture"
sections — this gives you the whole shape (four planes, thirteen capabilities, one durable event log) in
about five minutes, without yet needing the full design reference. The one sentence to hold onto: **Nexus
turns a Goal into governed, auditable, replayable execution** — every decision about what runs, when, and
whether it's allowed is deterministic and rule-based, never left to the LLM runtime doing the work.

### 5. Continue into the tutorials (ongoing)

[`docs/tutorials/`](../tutorials/) — ten guided tutorials, each teaching one concept and pointing at a
runnable example. Start at [Tutorial 01](../tutorials/01-installing-nexus.md) (you've basically already
done it) or jump straight to [Tutorial 02](../tutorials/02-first-pipeline.md) since you just ran that
example.

## What "success" looks like at each step

| Step | Success signal |
|---|---|
| Clone | `nexus/` directory exists locally with `.git/` present |
| Install | `uv sync` exits 0; `.venv/` (or `uv`'s managed environment) exists |
| First example | Console output ends with `status: completed`, `succeeded: True` |
| Architecture | You can name the four planes (Reasoning & Grounding, Planning & Governance, Execution, Post-Execution) and explain what the durable event log is for, in your own words |
| Tutorials | You've run at least Tutorials 01–03 and understand why the pipeline has nine fixed-order stages |

## Troubleshooting

- **`ModuleNotFoundError: No module named 'nexus_...'`** — `uv sync` didn't complete. Re-run it from the
  repository root and check for errors before retrying the example.
- **`UnicodeEncodeError`** (Windows) — a real platform behavior, not a bug: some log output (policy
  reasoning traces) includes non-ASCII characters. Every example already handles this internally
  (`sys.stdout.reconfigure(encoding="utf-8")`); if you're copying code out of an example, carry that line.
- **`uv: command not found`** — install `uv` per its own docs (https://docs.astral.sh/uv/getting-started/installation/),
  then retry step 2.
- **Anything else** — [`docs/development/DEVELOPMENT.md`](../development/DEVELOPMENT.md) §8 has more
  platform-specific notes; [`docs/development/CONTRIBUTING.md`](../development/CONTRIBUTING.md) explains
  how to open an issue if you're still stuck.

## Where to go from here

| I want to... | Go to |
|---|---|
| Learn by running examples in a guided order | [`docs/tutorials/`](../tutorials/) |
| See every example without a guided narrative | [`examples/`](../../examples/) |
| Read the full architecture reference | [`docs/architecture/README.md`](../architecture/README.md) |
| Understand why specific decisions were made | [`adr/README.md`](../../adr/README.md) |
| See what's actually been measured | [`docs/benchmarks/README.md`](../benchmarks/README.md) |
| Contribute code | [`docs/development/CONTRIBUTING.md`](../development/CONTRIBUTING.md) |
