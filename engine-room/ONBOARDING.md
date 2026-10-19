# Nexus — Onboarding Guide

> For new contributors and anyone joining the Nexus project.
>
> **This guide onboards you to Nexus v1** (`nexus/`, released as `v1.0.0`/`v1.0.1`). For the v2
> platform (`nexus_*` packages, released as `v2.0.0`), start with
> [docs/internals/WALKTHROUGH-v2.md](docs/internals/WALKTHROUGH-v2.md) instead. See
> [docs/README.md](docs/README.md) if you're not sure which one you need.

---

## Welcome

Nexus is an **AI Orchestration Control Plane**.

Before writing a single line of code, you must understand what Nexus is, what it is not, and why it was built the way it was.

This guide walks you through that understanding.

---

## Step 1: Read the Source of Truth

Read every document in `docs/` in order. They are the source of truth:

| Document | Reading Time | Key Takeaway |
|---|---|---|
| [00_BRIEF.md](docs/v1/00_BRIEF.md) | 10 min | Vision, purpose, what Nexus is and is not |
| [01_ARCHITECTURE.md](docs/v1/01_ARCHITECTURE.md) | 15 min | Six-layer architecture, data flows |
| [02_TECH_STACK.md](docs/v1/02_TECH_STACK.md) | 5 min | Technology choices |
| [03_AGENT_DESIGN.md](docs/v1/03_AGENT_DESIGN.md) | 10 min | Agent taxonomy, routing, memory model |
| [04_INTEGRATION_SPECS.md](docs/v1/04_INTEGRATION_SPECS.md) | 15 min | Integration contracts and event flows |
| [05_CRITICAL_CONSTRAINTS.md](docs/v1/05_CRITICAL_CONSTRAINTS.md) | 10 min | **Read twice. These are non-negotiable.** |
| [06_DEVELOPMENT_PHASES.md](docs/v1/06_DEVELOPMENT_PHASES.md) | 10 min | Build order and phase exit criteria |
| [07_NEXUS_AGENT.md](docs/v1/07_NEXUS_AGENT.md) | 10 min | External references and evaluation requirements |
| [08_MEMORY_ARCHITECTURE.md](docs/v1/08_MEMORY_ARCHITECTURE.md) | 10 min | Memory philosophy, domains, patterns |
| [RULES.md](docs/v1/RULES.md) | 10 min | **Operating rules for all contributors** |

---

## Step 2: Understand the Core Model

### Nexus Is NOT a Chatbot

```
WRONG:
User → LLM → Action

CORRECT:
User → Nexus (orchestrator) → Approval → Agent → Audited Result
```

### The Six Layers

```
1. Communication Layer    ← Discord, Email (external interfaces)
2. Event Gateway          ← Normalize, validate, route
3. Nexus Core             ← Orchestration: Task Engine, Approval Engine, Agent Router
4. Memory + Scheduling + Intelligence  ← Persistence, time-based triggers, LLM reasoning
5. Execution Layer        ← Gemini CLI, Claude Code, Hermes Agent
6. Repository Layer       ← Only allow-listed repositories
```

### The Three Non-Negotiable Axioms

1. **Memory is mandatory.** Every workflow must persist and survive restart.
2. **Humans approve execution.** No agent executes without a recorded approval.
3. **LLMs are tools, not authorities.** They reason; Nexus decides.

---

## Step 3: Read the Blueprint

The `blueprint/` directory is the project's living memory:

- [blueprint/ROADMAP.md](blueprint/ROADMAP.md) — Full phased execution plan
- [blueprint/STATUS.md](blueprint/STATUS.md) — Current status snapshot
- [blueprint/GAPS_AND_RISKS.md](blueprint/GAPS_AND_RISKS.md) — Open questions and risks
- [blueprint/DECISIONS/](blueprint/DECISIONS/) — All architectural decisions (ADRs)

---

## Step 4: Set Up Your Environment

Follow [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions.

---

## Step 5: The 27 Constraints

Read `docs/v1/05_CRITICAL_CONSTRAINTS.md` one more time. These 27 constraints are the laws of Nexus.

The most critical:

| # | Constraint |
|---|---|
| 1 | Human governance is mandatory — no AI approvals |
| 2 | Memory is mandatory — stateless design is forbidden |
| 5 | LLMs are reasoning engines — not authorities |
| 6 | Execution must be controlled — always approved, always audited |
| 7 | No arbitrary repository access — allow-list only |
| 9 | Deterministic routing — never LLM-based |
| 10 | Every workflow must be recoverable |
| 11 | Every action must be auditable |
| 20 | No hidden state — everything in Memory Manager |
| 23 | Testability is mandatory |
| 26 | MVP means minimal scope + production quality |
| 27 | No silent automation — every action must be explainable |

---

## Step 6: Pick Up Your First Task

Tasks are tracked in `blueprint/ROADMAP.md`.

Nexus v1 is past Phase 0 — it has shipped `v1.0.0` ("Operational Intelligence") and is in the
`v1.0.1` "Alignment" line. For the current, authoritative list of in-progress and next-available work,
read [blueprint/STATUS.md](blueprint/STATUS.md) (current status) and
[blueprint/ROADMAP.md](blueprint/ROADMAP.md) (full phased plan) directly rather than relying on a task
list fixed at onboarding-guide-writing time — those two files are kept current; this guide is not.

When you start an AP:
1. Update its status in `blueprint/ROADMAP.md` to 🔄 In Progress
2. Create the AP directory: `blueprint/phases/phase-N/AP-NNN/`
3. Fill in `SPEC.md`, `IMPLEMENTATION.md`, `DECISIONS.md`, `STATUS.md`

When you complete an AP:
1. Update status to ✅ Complete
2. Commit blueprint updates alongside code changes

---

## Common Pitfalls (Don't Do These)

| ❌ Wrong | ✅ Right |
|---|---|
| Store state in Discord messages | Store state in Memory Manager |
| Let an LLM approve an execution | Require human approval through Discord |
| Route agents based on LLM classification | Use the routing table in AgentRouter |
| Skip tests | Write unit + integration + e2e tests |
| Execute against any repository | Only execute against registered repositories |
| Use `print()` for logging | Use `structlog` with structured fields |
| Build without documenting | Update blueprint with every decision |
| Hard-delete records | Soft-archive with `is_archived = True` |

---

## Questions?

If anything is unclear, ambiguous, or conflicting — **stop and ask**.

Open an issue with your precise question.

Do not guess. Do not invent requirements.

This is a production-grade control plane, not a hackathon project.
