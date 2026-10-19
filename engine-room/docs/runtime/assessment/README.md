# OmniRoute — Runtime Adapter Compatibility Assessment

**Type:** architectural due-diligence only. **No integration, no code, no configuration
change, no commit.** This directory decides *whether* OmniRoute could become a first-class
Runtime Adapter within the Nexus Runtime architecture — on architecture, not convenience.

**Subject:** [OmniRoute](https://github.com/diegosouzapw/OmniRoute) — a local,
OpenAI-compatible AI gateway (MIT, Next.js/TypeScript, Node ≥ 22). Cloned for inspection at
`D:/_eval/OmniRoute` (**scratch eval dir — not part of the Nexus tree**), version 3.8.42.

**Assessed against (frozen, authoritative):** `docs/v2/runtime/00…20`, the Runtime Core
implementation in `nexus_runtime/`, `contracts/`, `adr/`, and
`docs/v2/99_ARCHITECTURAL_INVARIANTS.md`.

---

## The one finding that governs everything

> **OmniRoute is a chat-completions LLM gateway. The Nexus Runtime Adapter contract
> (`03_RUNTIME_ADAPTERS.md`) describes *task-executing* runtimes.** They are at different
> altitudes. OmniRoute is not a Runtime; it is the kind of provider transport that a
> future **LLM/Model Runtime adapter** would *call*. Forcing OmniRoute to *be* a Runtime
> Adapter is a category error; placing it *behind* one is legitimate and cheap.

Every section below is an elaboration of that altitude gap and its consequences.

## Verdict

**APPROVE WITH CONSTRAINTS** — see `08_RECOMMENDATION.md` for the full reasoning and the
binding constraint list. In one line: *not as a Runtime, not now, and never in RM core; but
acceptable later as the optional, sandboxed provider backend of a Nexus-authored LLM
Runtime adapter, under strict security and operational constraints, with OpenRouter-direct
remaining the default.*

## Reading order

| Doc | Question it answers |
|---|---|
| `01_COMPATIBILITY.md` | Does OmniRoute's surface line up with the adapter's nine concerns? |
| `02_ARCHITECTURAL_FIT.md` | Where (if anywhere) does it sit in the platform spine without leakage? |
| `03_OPERATIONAL_RISKS.md` | Dependency footprint, maintenance, update cadence, complexity. |
| `04_SECURITY_REVIEW.md` | Does it violate `.env`-single-source and the security spine? |
| `05_TOOL_CALLING.md` | Native tool-calling reality: OmniRoute vs OpenRouter vs no-auth providers. |
| `06_FAILURE_MODES.md` | Can the Runtime Manager absorb its failures without architectural change? |
| `07_RUNTIME_MAPPING.md` | Conceptual mapping RM → Session → adapter → OmniRoute → provider. |
| `08_RECOMMENDATION.md` | APPROVE / APPROVE WITH CONSTRAINTS / REJECT + the seven explicit answers. |

## Evidence base

- **Nexus side:** the 21 frozen `docs/v2/runtime/*` design docs and the shipped
  `nexus_runtime/` package (Phase 8A).
- **OmniRoute side:** direct source inspection of `D:/_eval/OmniRoute` — file paths and
  identifiers are cited inline in each doc. Where a claim could not be grounded in source it
  is marked *unverified* rather than asserted.
