# Repository Intelligence

Status: Target Architecture (design only)

---

# Purpose

This document answers a specific architectural question:

> Should Repository Intelligence be **inside** Engineering Intelligence, or its **own** subsystem?

**Verdict: its own subsystem.** Repository Intelligence is a *source of understanding* that
Engineering Intelligence (and Context Engineering) **consume** read-only. It is not part of EI.

This document justifies that verdict and specifies the seam.

---

# What Repository Intelligence is

Repository Intelligence is the subsystem that turns a repository into **facts about a repository**.

It indexes and serves:

- structure — directories, modules, entry points, build/test presence;
- languages and frameworks in use;
- architectural markers — ADRs, contracts, invariants, conventions;
- change history — recent commits, churn, ownership;
- known prior failures — references to past validated failures tied to areas of the code;
- health signals — test coverage presence, dependency state.

It serves these as **references and facts, never embedded content** (INV-27), through a read-only
**Repository Understanding** artifact.

---

# Why it is NOT inside Engineering Intelligence

Four independent reasons, each sufficient:

## 1. One responsibility per subsystem (INV-02)

EI's single responsibility is *deciding the engineering approach*. Repository Intelligence's is
*acquiring and serving repository facts*. Folding acquisition into EI would give EI two
responsibilities and violate INV-02 — the same reason Knowledge is not inside Reflection, and
Context is not inside Planning.

## 2. Different lifecycle

Repository facts have an **indexing lifecycle**: build an index, cache it, invalidate on change,
incrementally update. EI has a **decision lifecycle**: read a situation, emit a strategy, done. These
cadences are unrelated; binding them couples a slow, stateful I/O subsystem to a fast, stateless
cognitive one.

## 3. Multiple consumers

EI is not the only consumer. **Context Engineering** also needs repository facts to assemble the
Context Package (`../03`). If Repository Intelligence lived inside EI, Context Engineering would have
to reach *through* EI to get repository facts — an upward dependency that violates INV-01. As a
separate subsystem, both consume it read-only, independently.

## 4. Different failure model

Repository indexing can fail, be stale, or be partial (a huge monorepo, a network mount). That is an
*availability* concern with retries and caching. EI must *tolerate* partial or absent Repository
Understanding (`02`) — but it should not *own* the machinery that produces it, any more than Planning
owns the Knowledge store it reads.

---

# The seam

```
Repository ──► Repository Intelligence ──► Repository Understanding (read-only)
                                                │
                                 ┌──────────────┴───────────────┐
                                 ▼                              ▼
                     Engineering Intelligence          Context Engineering
                     (grounds the approach)            (assembles the context)
```

- **Repository Intelligence** produces facts. It never decides an approach, gathers a Context
  Package, plans, or executes.
- **Engineering Intelligence** consumes facts to *ground its strategy* — to classify the work and
  assess risk against what the repository actually is.
- **Context Engineering** consumes facts to *assemble context* the Strategy's Context Objectives
  call for.

The two consumers use the *same* Repository Understanding for different purposes. Neither owns it.

---

# Relationship to Harnesses

Repository Intelligence is naturally a **Harness-category capability** (INV-34/35): it integrates an
external system (a version-controlled repository / filesystem) and exposes a capability
(repository-understanding) without leaking provider details or performing business logic. This
places it cleanly in the existing architecture — it is *how* the platform learns a repository, the
same way a Runtime is *how* the platform executes. Its availability and health live in the Harness
Registry (INV-36), and it is provider-independent (git, hg, a hosted API — all behind the harness).

> This document specifies Repository Intelligence only to the depth EI needs to consume it. A full
> Repository Intelligence architecture package (its own `docs/v2/repository/`) is a named,
> deferred extension (`14`). This design does not pre-empt it; it only fixes the *seam and the
> ownership verdict*.

---

# What EI relies on from it

EI depends on Repository Understanding for:

- **Classification** — is there code? tests? what languages? (a "bug fix" in a tested Python service
  differs from one in an untested shell script).
- **Risk** (`09`) — blast radius and reversibility depend on what the change touches and whether the
  repo has tests and revert paths.
- **Context Objectives** (`03`) — EI names *what to understand* grounded in what actually exists.

Absent Repository Understanding, EI degrades to a conservative default (tighter risk envelope, lower
autonomy) rather than assuming — consistent with the uncertainty-raises-risk rule (`09`).

---

# Boundary summary

| Concern | Owner |
|---|---|
| Index and serve repository facts | **Repository Intelligence (separate subsystem)** |
| Consume facts to decide the approach | Engineering Intelligence |
| Consume facts to assemble context | Context Engineering |
| Embed file content | nobody — reference only (INV-27) |
| Track provider/health of the repo source | Harness Registry (INV-36) |

---

# North Star

Repository Intelligence knows the system. Engineering Intelligence decides what to do about it.
Context Engineering gathers what the doing will need.

Three responsibilities, three subsystems, one read-only artifact between them.
