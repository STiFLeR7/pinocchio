# Autonomy Model

Status: Target Architecture (design only)

---

# Purpose

This document defines how Engineering Intelligence determines the **autonomy level** of a piece of
work — how much may proceed without human approval, and where approval gates belong — while keeping
human governance final (Vision: "Autonomy never replaces accountability").

---

# Autonomy is proposed, never seized

Engineering Intelligence *proposes* an autonomy level as a facet of the Strategy. It does not grant
itself authority. Two invariants bound it:

- **Governance authorizes; it never executes** (INV-29). EI's proposed autonomy is subject to policy
  evaluation by the Policy Engine (INV-28).
- **Governed actions fail closed** (INV-30). Where policy does not permit unattended action, the
  default is human approval, not autonomous proceed.

So EI's autonomy facet is a *request within a ceiling*, and the ceiling is Governance's.

---

# The autonomy ladder

EI selects a level from a fixed, ordered ladder. Higher levels require lower risk and permissive
policy; the coherence rules (`04`) enforce the relationship.

| Level | Meaning | Typical fit |
|---|---|---|
| **Observed** | Platform proposes; human performs every consequential action | first contact with a new repo/operator; unknown risk |
| **Gated** | Platform proceeds, pausing for approval at each irreversible/consequential step | production-touching work; medium-high risk |
| **Supervised** | Platform proceeds unattended but streams progress and can be interrupted; approval only at defined gates | normal engineering with reversible steps |
| **Autonomous** | Platform completes the work and reports; no approval gates | low-risk, fully reversible, high-confidence, policy-permitted |

The ladder is monotonic with trust: more autonomy demands lower risk (`09`), stronger validation
rigor (`07`), and explicit policy permission.

---

# Gate placement

Choosing a level is not enough; EI also decides **where the gates are**. A gate is an approval point
tied to a specific consequential action.

EI places a gate before any action that is:

- **irreversible or hard to reverse** — commit to a shared branch, deploy, delete, send an external
  message;
- **outside the risk envelope** (`09`);
- **policy-flagged** as approval-required (INV-28).

Example (reference bug-fix): level `Supervised`, with gates `before commit` and `before report-
send` — the reversible investigation and patching proceed unattended; the two outward/irreversible
actions require a human.

Gates are expressed as *intent*; Governance and Orchestration enact them (Orchestration owns
pause/resume, INV-23; Governance owns the approval decision, INV-29).

---

# Why autonomy lives in EI

Autonomy is an engineering judgment, not a runtime setting. Deciding "this is safe to do unattended,
but that step needs a human" requires the same situational awareness EI already holds: the
classification, the risk, the reversibility, the operator's preference, and the policy ceiling. No
other layer holds all of these at once:

- Governance holds policy but not the engineering context that makes a step consequential.
- Orchestration enacts pause/resume but does not decide *where* pauses belong.
- The operator holds preference but should not have to hand-place every gate on every goal.

EI composes these into a coherent autonomy proposal — the same coherence argument that justifies the
layer (`01`).

---

# Human authority remains final

The autonomy model never erodes human accountability:

- Every gate is a real approval point a human can reject (INV-29).
- Every autonomous proceed is *within* an explicit, recorded, policy-permitted envelope.
- The autonomy level and every gate carry rationale and are auditable (INV-31).
- When uncertain, EI proposes *less* autonomy (fails closed, INV-30). Clarification and approval are
  preferred over unsupervised risk — the same principle Intent Resolution applies to ambiguity
  (`../16`).

---

# Interaction with preferences and learning

- **Preferences** set an operator's default autonomy comfort (some operators want `Autonomous` for
  routine work; others want `Gated` always). EI honors this within policy (`02`).
- **Learning** adjusts defaults over time: if an operator repeatedly approves a class of action
  without change, Reflection can observe that and Knowledge can raise the learned comfort — EI
  consumes the result (`13`). EI never raises its own autonomy directly; the loop runs through
  Reflection → Knowledge (INV-25/26).

---

# Boundary summary

| Autonomy facet | Enforced by |
|---|---|
| ✓ EI proposes an autonomy level | own responsibility |
| ✓ EI places approval gates as intent | own responsibility |
| ✓ EI scales autonomy inversely with risk | coherence rule (`04`, `09`) |
| ✗ EI never grants itself authority | Governance authorizes (INV-29) |
| ✗ EI never enacts pause/resume | Orchestration (INV-23) |
| ✗ EI never bypasses policy | Policy Engine (INV-28), fail-closed (INV-30) |
| ✗ EI never raises its own autonomy from experience directly | Reflection → Knowledge (INV-25/26) |

---

# North Star

Engineering Intelligence proposes how much to trust the machine, and marks exactly where the human
must stay in the loop.

Autonomy is earned by low risk and permitted by policy. Accountability is never delegated.
