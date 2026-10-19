# Runtime Strategy

Status: Target Architecture (design only)

---

# Purpose

This document defines how Engineering Intelligence expresses **runtime preference**, and why that
never crosses into runtime *selection*, which is Orchestration's alone (INV-37).

---

# The hard boundary: preference vs. selection

The frozen architecture is unambiguous:

> **INV-37 — Runtime selection is Orchestration's; capability resolution returns candidates only.**

Engineering Intelligence sits far above Orchestration. It must never select a runtime, and it must
never reference a provider (INV-32). What it *can* do is express the **capability posture** the work
demands, so that when Orchestration selects, it selects for the right characteristics.

| Question | Owner |
|---|---|
| "What capability posture does this work need from a runtime?" | **Engineering Intelligence** |
| "Which registered runtimes offer those capabilities and are healthy?" | Capability resolution / Harness Registry (INV-36) |
| "Which one runs this Work Package?" | Orchestration (INV-37) |

---

# What EI produces: Runtime Preferences

A **Runtime Preference** in the Engineering Strategy is:

- a set of **preferred capabilities** the runtime should have (e.g., high context window,
  code-generation, filesystem access, VCS operations, tool use), referenced by the frozen Capability
  model — **never a provider or model name**;
- **soft constraints** — "avoid low-context runtimes for this refactor"; "prefer a runtime that
  supports interactive approval callbacks for the gated step";
- **rationale** (INV-31).

Example:

```
Runtime Preferences:
  prefer:  [ code-generation, high-context, filesystem, version-control ]
  avoid:   [ low-context ]  (for the implementation phase)
  rationale: a multi-file surgical fix with regression proof needs code + fs + VCS capability
             and enough context to hold the module and its tests at once
```

EI names capabilities. It never names Claude, Gemini, a shell, or a model version.

---

# Why this solves the "work-characteristic-aware selection" gap

The operational gap analysis found that runtime selection today is *policy-only*: because all work
maps to an abstract capability, selection cannot distinguish a code-fix from a shell task. The
missing input was a **work-characteristic classifier** feeding capability posture into selection.

Engineering Intelligence *is* that classifier's home. By classifying the work (`04`) and deriving a
capability posture from the classification, EI supplies exactly the input that makes Orchestration's
selection characteristic-aware — **without EI selecting anything**. Orchestration still chooses,
still applies policy, still honors health (INV-36/37); it simply now chooses *for the right
capabilities* instead of a single abstract one.

---

# Feasibility: preferences must be realizable

EI reads Environment Facts (`02`) — available capabilities and health from the Harness Registry
(INV-36). Its Runtime Preferences must be a subset of capabilities some healthy harness can provide
(a coherence rule, `04`). EI never prefers a capability that does not exist in the environment; that
would produce an unrealizable Strategy.

If the environment lacks a needed capability, EI does not fail silently — it surfaces the gap in the
Strategy (typically raising the autonomy requirement to "human approval" or marking the work
blocked), so the shortfall is explicit rather than discovered at execution time.

---

# Provider independence — permanently

Runtime Preferences are the facet most tempting to bind to a provider ("use Claude for this"). The
design forbids it, forever:

- EI reasons about **capabilities**, per the Vision principle *Capabilities over Models* and INV-32.
- The reasoning engine EI *itself* uses is accessed as a runtime/harness capability and is likewise
  replaceable.
- Because no facet ever names a provider, swapping, adding, or retiring a runtime changes nothing in
  EI. This is the same property that lets the same Skill run on any runtime (INV-33), applied one
  layer up.

See `13` for the full provider-independence argument.

---

# Boundary summary

| Runtime Strategy facet | Enforced by |
|---|---|
| ✓ EI declares preferred/avoided capabilities | Capability model (INV-32) |
| ✓ EI supplies work-characteristic posture to selection | closes the selection gap |
| ✓ EI keeps preferences realizable | Harness Registry facts (INV-36) |
| ✗ EI never selects a runtime | Orchestration (INV-37) |
| ✗ EI never names a provider/model | provider independence (INV-32) |
| ✗ EI never resolves capability candidates | capability resolution (INV-37) |

---

# North Star

Engineering Intelligence says what *kind* of runtime the work deserves.

Orchestration decides *which* runtime, from healthy candidates, under policy. EI describes the need;
it never makes the choice.
