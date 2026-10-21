# Nexus v2 — Execution Actuation Architecture (design only)

> **Status:** Architecture & design specification. **No implementation.** This directory
> defines *what* the Execution Actuation Layer is and *how* it must behave, so that a future
> implementation team can build it without making new architectural decisions. It introduces
> **no** production code, Protocols, classes, algorithms, or APIs. It amends **no** ADR,
> contract, or invariant; where the existing architecture needs clarification, that is recorded
> as a *recommendation* in [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md), not applied.
> It expands the space the Runtime layer explicitly left **behind the Runtime Adapter boundary**
> (`../runtime/03_RUNTIME_ADAPTERS.md` §3, `../runtime/00_RUNTIME_OVERVIEW.md` §4); it never
> contradicts the Runtime, Execution, Validation, or Recovery architectures.

## Why this exists

Nexus prepares work completely. Orchestration nominates runtimes, the Runtime Manager allocates a
**Runtime Session**, and the Execution Engine drives it through a **Runtime Adapter**. Everything up
to the adapter boundary is specified and running.

The Runtime layer draws a bright line and stops at it:

> *"All provider knowledge lives behind the Runtime Adapter boundary."* — `../runtime/00` §1
> *"This document is conceptual. It introduces no interface signature, no method list, no
> algorithm."* — `../runtime/03` §preamble

**Behind that boundary is where real, governed action in an external engineering environment
actually happens** — launching Claude Code in a repository, opening a shell, holding a session alive
for hours, writing files, running `git commit`, driving a browser, connecting to an MCP server. The
Runtime layer names the boundary and the *rules* action must honor (isolation, least privilege,
secret handling, governance — `../runtime/17`, `../runtime/18`); it does not model the **external
world** those actions operate on, nor provide a home for the actions themselves.

Today that space is implicit — it would be re-invented, per provider, inside each adapter's private
code, with duplicated workspace handling, duplicated permission enforcement, and no shared model of
a long-lived environment. **Execution Actuation is that space, specified once as a shared,
uniformly-governed substrate.** It answers exactly one question:

> Given a prepared Runtime Session bound to an allocated runtime, **how are governed actions safely
> carried out inside an external engineering environment** — modeling the environment, its
> workspace, and its live (possibly long-lived, reattachable) session; enforcing the permission
> envelope on every action; emitting an auditable action stream; and surfacing produced artifacts
> as Evidence Candidates — without Actuation ever deciding *what* to run, *which* runtime, or
> *whether* the work succeeded?

**Execution decides what. Runtime selection decides where. Execution Actuation carries it out, and
Validation decides whether it worked.** That sentence is the spine of every document here.

## Relationship to the Runtime layer (stated up front)

Execution Actuation does **not** replace or modify the Runtime Manager, the Runtime Adapter contract,
the Runtime Session, runtime selection, or the `runtime.*` events. All of that remains exactly as
specified. Actuation is the **shared realization substrate the adapters are built on**:

- The Runtime **Adapter** remains the nine-concern conceptual contract (`../runtime/03` §2).
- Actuation supplies the **objects and primitives** an adapter uses to satisfy that contract —
  first-class `Environment`, `Workspace`, and (long-lived, reattachable) actuation `Session`, plus
  the governed filesystem / git / terminal / process / MCP primitives — so an adapter becomes a thin
  provider translation over a shared, uniformly-governed base rather than bespoke private code.
- Actuation **honors, consolidates, and enforces** the Runtime security (`../runtime/17`) and
  governance (`../runtime/18`) rules at the *action* granularity, one level finer than the
  session-lifecycle granularity the `runtime.*` events model.

`nexus_actuation → { nexus_core, nexus_infra }` only. RM core stays generic and unchanged; the only
code that ever depends on Actuation is the provider-specific adapter code that already lives behind
the boundary.

## What Execution Actuation is NOT

| Concern | Owner — **not** Actuation |
|---|---|
| Decide *what* work to perform | Planning / Work Packaging (INV-03) |
| Decide *which* runtime performs it | Orchestration nominates, RM allocates (INV-37) |
| Prepare and own the Runtime Session (the per-attempt binding) | Runtime Manager (`../runtime/02`) |
| Decide the engineering approach | Engineering Intelligence (`../engineering/`) |
| Observe health; recommend intervention | Supervision (INV-11/23) |
| Determine completion from evidence | Validation (INV-20/21) |
| Decide recovery | Recovery (INV-22) |
| Evaluate governance policy | Policy Engine (INV-28) |
| Store durable understanding | Knowledge Engine (INV-25) |

Actuation **operates**. It decides nothing about what, which, whether, or what-next.

## Reading order

| # | Document | Defines |
|---|---|---|
| — | [`00_OVERVIEW.md`](00_OVERVIEW.md) | The subsystem, placement behind the adapter boundary, inputs/outputs, dependency direction, canon glossary |
| — | [`01_EXECUTION_ACTUATION.md`](01_EXECUTION_ACTUATION.md) | Responsibilities, the actuate pipeline, hard boundaries |
| — | [`02_ACTUATION_MODEL.md`](02_ACTUATION_MODEL.md) | Actuator, Actuation Command / Interaction, the realization of the adapter's nine concerns |
| — | [`03_ENVIRONMENTS.md`](03_ENVIRONMENTS.md) | The `Environment` — the isolated locus of actuation |
| — | [`04_SESSIONS.md`](04_SESSIONS.md) | The `Session` — the live, long-lived, reattachable interaction |
| — | [`05_WORKSPACES.md`](05_WORKSPACES.md) | The `Workspace` — the filesystem/repository scope and git operations |
| — | [`06_PERMISSIONS.md`](06_PERMISSIONS.md) | The Permission Envelope and per-action enforcement |
| — | [`07_GOVERNANCE.md`](07_GOVERNANCE.md) | Policy Engine decides, Actuation enforces; approval gates; audit |
| — | [`08_EVENT_MODEL.md`](08_EVENT_MODEL.md) | The canonical `actuation.*` event taxonomy |
| — | [`09_FAILURE_MODEL.md`](09_FAILURE_MODEL.md) | Typed failures; Actuation reports, never decides recovery |
| — | [`10_RECOVERY_INTEGRATION.md`](10_RECOVERY_INTEGRATION.md) | resume / reattach / recreate / restart — mechanisms, not decisions |
| — | [`11_SECURITY.md`](11_SECURITY.md) | Secret references, least privilege, redaction, blast radius, teardown |
| — | [`12_EXTENSIBILITY.md`](12_EXTENSIBILITY.md) | Absorbing new actuators without redesign |
| — | [`13_GAPS.md`](13_GAPS.md) | Open questions and deferred decisions |
| — | [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md) | Correctness, completeness, readiness, ratification verdict |

## Canon (binding for every document)

- **Execution Actuation Layer** — the subsystem specified here. Operates external environments;
  never decides what/which/whether/what-next.
- **Actuator** — the provider-specific driver that operates one environment kind (Claude Code,
  shell, Docker, browser, MCP, remote…). It is what *satisfies* a Runtime Adapter's nine concerns
  (`../runtime/03` §2) using the shared Actuation substrate. Registered as a Harness (INV-36).
- **Environment** — the isolated locus where actuation happens (local machine, container, remote
  host, K8s pod). Carries the isolation surface (`../runtime/17` §2).
- **Workspace** — the filesystem/repository scope inside an Environment; the unit of filesystem and
  git permissioning (`05`).
- **Session** — the live, stateful, event-sourced, **long-lived and reattachable** interaction with
  an Actuator inside an Environment. Distinct from the RM-owned per-attempt **Runtime Session**; one
  Session may serve multiple Runtime Session attempts (reattach — `04`, `10`).
- **Permission Envelope** — the scoped set of permitted action classes for a Session, derived from
  the package's declared requirements + resolved Policy bundle; enforced per action (`06`).
- **Dependency direction** — `nexus_actuation → { nexus_core, nexus_infra }` only. Actuation is
  consumed by provider-specific adapter code (behind the Runtime Adapter boundary) and by nothing in
  the RM core or any upstream layer.
- **Binding invariants** — INV-04 (Actuation never plans), INV-09/19 (only Work Packages reach a
  runtime), INV-11 (Execution emits events; Supervision observes), INV-12 (Evidence Candidates, not
  Evidence), INV-13/14 (event-sourced state), INV-17 (timestamps/non-determinism as data), INV-18
  (checkpoint-aware), INV-20/21 (Validation decides completion), INV-22 (Recovery decides
  continuation), INV-27 (reference, never embed), INV-28/29/30 (Policy Engine evaluates; fail
  closed), INV-31 (auditable), INV-32 (provider-independent capabilities), INV-36 (Harness Registry
  owns availability/health), INV-39 (correlated events). No document may weaken these. The `.env`
  secret spine (`../runtime/17` §1) is likewise binding and never contradicted.
