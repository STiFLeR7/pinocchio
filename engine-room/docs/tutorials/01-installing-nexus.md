# Tutorial 01 — Installing Nexus

## What you'll learn

How to install Nexus v2, why the repository contains two unrelated codebases, and how to verify your
install actually works before writing anything.

## Concept: two products, one repository

This repository holds **Nexus v1** (`nexus/`, a Discord-fronted control plane, released `v1.0.0`/`v1.0.1`)
and **Nexus v2** (`nexus_*`, 31 packages, an event-sourced constitutional reasoning spine, released
`v2.0.0`). They share one git history and one `pyproject.toml` and nothing else — no shared code, schema,
or process. These tutorials are entirely about **v2**. If you meant to work on v1, stop here and read
[`ONBOARDING.md`](../../ONBOARDING.md) instead.

## Steps

```bash
git clone https://github.com/STiFLeR7/nexus.git
cd nexus
uv sync
```

That's the entire install. [`uv`](https://docs.astral.sh/uv/) provisions the Python interpreter (3.12+)
and the exact locked dependency set — you do not need a pre-existing Python install, a virtualenv you
create by hand, or `pip`. v2's only third-party runtime dependency is `pydantic` (`>=2.0,<3`); there is no
database to stand up, no config file to copy, and no API key to obtain — every example and tutorial in
this series runs against deterministic stub runtimes with zero network access.

## Verify the install

```bash
uv run python examples/01-hello-nexus/run.py
```

If this prints a completed pipeline run (ending in `status: completed`), your install is correct and
you're ready for Tutorial 02, which explains exactly what that command just did. If it doesn't:

- **`ModuleNotFoundError: No module named 'nexus_...'`** — `uv sync` didn't run, or didn't finish. Re-run
  it and check for errors.
- **`UnicodeEncodeError`** on Windows — a real platform behavior (some log output includes non-ASCII
  characters), not an install failure. See [`examples/README.md`](../../examples/README.md#if-something-doesnt-run).
- Anything else — see [`docs/development/DEVELOPMENT.md`](../development/DEVELOPMENT.md) §8's Windows
  notes, or open an issue per [`docs/development/CONTRIBUTING.md`](../development/CONTRIBUTING.md).

## Check your understanding

- Why doesn't installing Nexus v2 require a database or an API key? (Because every example/tutorial uses
  deterministic stub runtimes and either an in-memory or local-SQLite-file durable log — see Tutorial 03.)
- What would go wrong if you ran `pip install -e ".[dev]"` from `CONTRIBUTING.md` (root) instead of
  `uv sync`? (That command installs **v1's** dependencies — a different, larger set including `fastapi`,
  `sqlalchemy`, and `discord.py` — none of which v2 needs or imports.)

## Go deeper

[`README.md`](../../README.md)'s own Installation section; [`docs/README.md`](../README.md) if you're
still unsure which codebase a file you're looking at belongs to.

## Next

[Tutorial 02 — Running Your First Pipeline](02-first-pipeline.md)
