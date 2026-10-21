# Governance

Status: Target Architecture (design only)

---

# Purpose

This document defines where **approval gates** sit in actuation, how Actuation enforces governance
without evaluating it, and how every governed action becomes an immutable audit record. It is the
action-granularity counterpart to Runtime Governance (`../runtime/18`), which governs at
session-allocation granularity.

---

# The posture

> The Policy Engine **evaluates** policy; Actuation **enforces** the resolved decision and **pauses**
> for approval. Actuation hardcodes no governance, invents no verdict, and **fails closed** — when a
> required decision or approval is unresolved, the action does not happen (INV-28/29/30).

Actuation is a **decide-nothing, enforce-and-record** layer. It sits below the Policy Engine, below
Governance, below Orchestration's approval coordination — it is the point where their decisions
finally bite on real actions.

---

# Two governance gates in actuation

Governance threads through actuation at two points:

```
Session provisioning
   │
   ├─ (1) ENVELOPE ENFORCEMENT  ─ every action checked against the Permission Envelope (06)
   │                              deny → actuation.command_denied, fail-closed
   │
   └─ (2) APPROVAL GATE         ─ a consequential action pauses for approval before it proceeds
                                  (../runtime/14 taxonomy; ../engineering/08 gate placement)
```

- **Envelope enforcement** answers "may this class of action occur at all?" — the permission model
  (`06`).
- **Approval gate** answers "should this specific consequential action proceed now?" — a pause, using
  the platform's single approval taxonomy (ADR-004, `../runtime/18` §4 `require_approval`).

---

# Where approval gates fall

Approval gates are placed **upstream** — Planning identifies gates, Engineering Intelligence proposes
their location as autonomy gates (`../engineering/08`), and Orchestration coordinates them
(`../runtime/18` §7). Actuation does not *decide* where a gate is; it **enacts the pause** when a
gated action is reached.

Typical gated actions at the actuation boundary (all consequential/irreversible — high blast radius,
`../engineering/09`):

| Gated action | Why gated |
|---|---|
| commit to a shared/protected branch | consequential; visible to others |
| **push / publish** | outward and hard to reverse |
| deploy / release | high blast radius, side effects |
| destructive filesystem action (bulk delete) | irreversible |
| outbound network to an external party (send a message) | leaves the platform (external-effect) |
| starting a high-cost or high-privilege Environment | cost/privilege ceiling (`../runtime/18`) |

At such an action, Actuation transitions the Session to a waiting state, emits the approval-pause
event, and **does not proceed** until the approval is granted (resume) or the taxonomy's
reject/timeout drives a terminal path (`../runtime/18` §4, `09`). Actuation **never decides** the
approval; the approver does.

---

# Policy Engine decides; Actuation enforces

```
Governance      ──defines──▶  Policy (data, ADR-004)
Policy Engine   ──evaluates──▶  PolicyDecision + ApprovalTaxonomy   (INV-28)
Harness         ──resolves──▶  Policy bundle on the Execution Package
Runtime Mgr     ──enforces at allocation──▶  eligibility / pause / refuse   (../runtime/18)
Execution       ──enforces at each action──▶  envelope check / approval pause / deny   (THIS layer)
```

- Actuation consumes the **already-resolved** Policy bundle (via the package/envelope); it never
  reaches back into Governance or the Policy Engine (dependency direction, `00`).
- Actuation hardcodes **no** allowed-list, cost rule, or approval rule; every such rule arrives as
  data and is enforced generically — so Actuation serves all runtimes, including unknown future ones
  (`12`).
- The closed `PolicyDecision` set (ADR-004) manifests at the action boundary exactly as it does at
  the runtime boundary (`../runtime/18` §4): `allow` proceeds; `deny` refuses the action;
  `require_approval` pauses; `delay`/`escalate`/`request_information` hold short of the action,
  fail-closed.

---

# Audit — every governed action on the record

Every governed action is an immutable, correlated event (INV-13/31/39). Because all actuation events
share the operation's `correlation_identifier`, governance gets a complete, tamper-evident trail from
Goal down to the individual `git commit`:

| Audited fact | Event (`08`) |
|---|---|
| action permitted and enacted | `actuation.command_executed` |
| action refused by envelope | `actuation.command_denied` |
| approval pause | `actuation.approval_requested` (waiting) |
| approval settled | `actuation.approval_resolved` / terminal, by causation link |
| workspace mutated | `actuation.workspace_modified` |
| artifact produced | `actuation.artifact_generated` |
| environment/session lifecycle | `actuation.environment_*` / `actuation.session_*` |

Properties (mirroring `../runtime/18` §5):

- **Immutable and one-way** — consumers (governance/audit/Operator) react to the log; none write back
  into Actuation state (INV-16).
- **End-to-end correlation** — a single Goal's governance lineage runs unbroken from Intent through
  the exact filesystem/git actions that touched the repository (INV-39).
- **No silent defaults** — every fail-closed refusal is itself an event; a denial is auditable, never
  invisible.

---

# Ownership

The bright line: **decide vs. enforce vs. record.** Actuation only enforces and records.

| Concern | Owner |
|---|---|
| Define policies | Governance |
| Evaluate policy → decision + taxonomy | Policy Engine (INV-28) |
| Identify approval gates | Planning |
| Propose autonomy gate placement | Engineering Intelligence (`../engineering/08`) |
| Coordinate/settle approvals | Orchestration |
| Make the approval grant/reject | the approver |
| **Enforce the envelope on each action; pause for approval; record** | **Execution Actuation** |

---

# North Star

Actuation is where every decision made above finally meets a real repository, a real terminal, a real
network call. It opens only permitted doors, stops at every gate a human must clear, and writes down
everything it did and everything it refused.
