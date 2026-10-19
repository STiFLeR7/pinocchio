# 18 — Runtime Governance

**Status:** design only. Defines where **policy checkpoints**, **approval checkpoints**,
and **audit boundaries** sit in the Runtime Manager, and who **owns** each governance
concern. The governing principle: the **Policy Engine evaluates** policies; **RM
enforces** the resulting constraints. RM hardcodes no governance (INV-28-style
discipline), invents no verdicts, and **fails closed** — when a required policy or
approval is unresolved, RM refuses to allocate.

---

## 1. The governance posture, stated first

> RM is an **enforcement point**, never a **decision point**. It reads the policy
> bundle the Harness already resolved (plus any runtime-scoped policy), it does not
> re-evaluate it. It pauses for approval (`14`) but does not decide it. It records
> every governed step as an immutable event (`15`). When anything required is missing
> or unresolved, it **denies** rather than proceeds.

Two non-negotiable rules frame everything below:

- **Separation (INV-28-style).** The Policy Engine *evaluates* policies and produces a
  closed `PolicyDecision`. RM *enforces* that decision at the runtime boundary. RM never
  inspects policy conditions, never resolves conflicts, never substitutes its own rule.
- **Fail-closed (INV-30-style).** Absence of a required, resolved governance signal is
  treated as **deny**, not allow. An unresolved policy, an unanswered approval, or a
  missing default never becomes implicit permission to allocate a runtime.

## 2. Where governance applies in the pipeline

Governance is not a single step; it threads through preparation. The two explicit gates
are pipeline steps 5 and 6 (`01` §4), backed by configuration-time constraints
(`17`).

```
Preparation pipeline (01 §4)            Governance role
------------------------------------    -----------------------------------------------
1  VALIDATE INTAKE
2  RESOLVE CANDIDATES
3  MATCH CAPABILITIES
4  FILTER HEALTH
5  APPLY POLICY            ◀───────────  POLICY CHECKPOINT: read the resolved bundle;
                                          enforce allowed-runtime / cost-ceiling /
                                          isolation constraints; map PolicyDecision (§4)
6  APPROVAL CHECKPOINT     ◀───────────  APPROVAL CHECKPOINT: if a decision is
                                          require_approval, PAUSE via file 14
7  SELECT
8  ALLOCATE                ◀───────────  PRIVILEGE GRANT: only reached if §5 and §6
                                          permit; this is where capacity is committed
9  CREATE SESSION
10 CONFIGURE               ◀───────────  ISOLATION ENFORCEMENT: render the isolation
                                          profile / least-privilege constraints (17)
11 READY → … → 14 RELEASE+DESTROY
```

The governed constraints RM enforces include, at minimum:

| Constraint | Source | Where enforced |
|---|---|---|
| **Allowed-runtime restriction** | policy bundle | step 5 — disallowed candidates become ineligible |
| **Runtime cost ceiling** | policy bundle / Strategy | step 5 — a candidate breaching the ceiling is ineligible; over-ceiling allocation refused |
| **Isolation requirement** | policy bundle (`17`) | step 5 (eligibility) + step 10 (rendered into the isolation profile) |
| **Approval requirement** | policy bundle (`require_approval`) | step 6 — pause via `14` |

> RM never *computes* a cost ceiling or *defines* an isolation level. It reads them as
> already-resolved constraints and **enforces** them. The numbers and rules come from
> Policy/Strategy; RM only checks candidates and configuration against them.

## 3. Policy Engine evaluates; RM enforces

The frozen `Policy` model (contract `policy.md`, ADR-004) is *evaluated only by the
Policy Engine* (INV-28). The bundle that reaches RM is an **already-resolved input**,
exactly as every prior layer consumed its predecessor's output.

```
Governance (owns)  ──defines──▶  Policy (data; conditions tree, decision, taxonomy)
                                        │
Policy Engine (owns)  ──evaluates──▶  PolicyDecision  +  (when require_approval)
                                        │                  ApprovalTaxonomy
Harness (Phase 6)  ──resolves into──▶  Policy bundle on the Execution Package
                                        │
Runtime Manager  ──READS & ENFORCES──▶  eligibility / pause / defer / refuse (§4)
```

- RM consumes the **Policy bundle the Harness already resolved**, plus any
  **runtime-scoped policy** attached to the Runtime Request — it does not reach back
  into Governance or the Policy Engine (dependency direction, `00` §4).
- RM **hardcodes no governance**: there is no allowed-list, cost rule, or isolation
  rule baked into RM core. Every such rule arrives as data and is enforced generically,
  so RM serves all runtimes including unknown future ones.
- Conflict resolution, specificity, versioning, and default-policy selection are the
  Policy Engine's (ADR-004). RM receives a *settled* decision and acts on it.

## 4. The closed decision set at the runtime boundary

`PolicyDecision` is a **closed set** (ADR-004 §3.2; recovery strategies are *not*
members). Each member has exactly one manifestation at the runtime boundary. RM
implements the *consequence*; it never re-derives the decision.

```
PolicyDecision        Manifestation in the Runtime Manager
--------------------  ----------------------------------------------------------------
allow                 Candidate remains eligible; preparation proceeds normally.
deny                  Candidate is INELIGIBLE. If denial removes all candidates, the
                      session is REFUSED — no allocation, fail-closed.
require_approval      APPROVAL CHECKPOINT: pause per file 14 (Waiting), carrying the
                      ApprovalTaxonomy; resume on grant, terminal on reject/timeout.
delay                 DEFER allocation: hold preparation (do not allocate yet) until
                      the delay condition clears; emit a governance event. No runtime
                      is reserved while delayed.
escalate              Emit a GOVERNANCE/ESCALATION event referencing the session and
                      the policy outcome; do not silently proceed. The escalation is
                      handled outside RM; RM holds fail-closed until resolved.
request_information   Treated as not-yet-allowed: RM cannot proceed on missing required
                      information; it surfaces the requirement as an event and holds
                      (fail-closed), never fabricating the missing input.
```

Cross-cutting guarantees:

- Only `allow` (and a resolved `require_approval`/`delay`) ever leads to **allocation**.
  `deny`, an unresolved `escalate`, `request_information`, or an unanswered approval all
  hold short of allocation — **no privilege escalation** (§6).
- `require_approval` is the single bridge from this document to `14`; the taxonomy on
  the policy (`Policy.approval_requirement`) selects the wait semantics there.
- RM maps the decision to a consequence **mechanically**. It never asks *why* a decision
  was made; the rationale lives on the `Policy` (`purpose` / `rationale`) and in audit.

## 5. Audit — the end-to-end trail

Every governance-relevant act in RM is an **immutable event** (`15`, ADR-001). Because
all runtime events share the operation's `correlation_identifier` (INV-39), governance
gets a complete, queryable, tamper-evident trail from candidate to terminal state.

| Audited fact | Event (`15`) | Why it matters for audit |
|---|---|---|
| candidates considered | `runtime.candidates_resolved` | what was eligible before policy |
| capabilities matched | `runtime.capabilities_matched` | basis for eligibility |
| **policy outcome / governance action** | governance/escalation events + the decision's effect | *what was decided and enforced* |
| **approval pause** | `runtime.waiting_approval` | a pause occurred; taxonomy + approval_ref |
| **approval decision (recorded)** | `runtime.resumed` / terminal (`14`) | who/what answered, by causation link |
| **allocation** | `runtime.allocated` | the moment privilege was granted |
| isolation/config applied | `runtime.prepared` (no secrets, `17`) | the enforced isolation profile |
| terminal state | `runtime.completed` / `cancelled` / `failed` / `timed_out` | outcome of the governed attempt |
| teardown | `runtime.released` / `runtime.destroyed` | privilege returned; nothing leaked |

Properties:

- **Immutable and one-way (INV-16 / `15` §5).** Consumers (governance/audit included)
  *react to* the log; none write back into RM session state.
- **End-to-end correlation (INV-39).** A single Goal's governance lineage —
  Goal → … → Harness → **Runtime** allocation/approval/outcome — is one causal stream.
- **Causation chains.** A `runtime.resumed` carries causation = the originating
  `runtime.waiting_approval` (and, transitively, the decision event), so *who authorized
  what* is reconstructable (`14` §4).
- **No silent defaults.** Every fail-closed refusal is itself an event (a typed
  failure/governance event), so a denial is auditable, never invisible.

## 6. Fail-closed discipline

When a required governance signal is **unresolved**, RM refuses to allocate. This is the
runtime-layer expression of INV-30 (the Default Policy denies) and the privilege rule of
`17`.

| Unresolved situation | RM's fail-closed behavior |
|---|---|
| no policy resolution available for a governed action | refuse allocation; surface a governance/failure event |
| all candidates denied / ineligible | refuse the session — no runtime allocated |
| approval required but no decision (or timed out, `14` §7) | terminal path; never an implicit grant |
| `escalate` / `request_information` outstanding | hold short of allocation until resolved |
| delay condition not yet cleared | defer allocation; do not reserve a runtime meanwhile |

> **No privilege escalation.** RM never grants more access than the resolved governance
> permits, and *missing* governance is treated as *least* privilege (none), not most. A
> runtime is allocated only when policy permits and any required approval is settled.

## 7. Ownership

The bright line: **decide vs. enforce vs. record.** RM only enforces and records.

| Concern | Owner | RM's relationship |
|---|---|---|
| Define policies (data: conditions, decision, taxonomy) | **Governance** | reads the resolved bundle only |
| **Evaluate** policies → `PolicyDecision` (+ taxonomy) | **Policy Engine** | consumes the verdict; never re-evaluates (INV-28) |
| Resolve the policy bundle onto the Execution Package | **Harness (Phase 6)** | consumes by value/reference (`00` §2) |
| Identify approval **gates** | **Planning** | not RM's concern |
| Coordinate / settle approval gates + taxonomy | **Orchestration** (`nexus_orchestration/approvals.py`) | aligns; enforces the pause, does not re-decide (`14` §6) |
| **Make** the approval grant/reject decision | **the approver** (any surface) | records it; never makes it (`14`) |
| **Enforce** policy constraints at the runtime boundary | **Runtime Manager** | this document |
| **Pause** the session for approval | **Runtime Manager** | `14` |
| **Allocate** the runtime once governance permits | **Runtime Manager** | `06` |
| Render isolation / least-privilege at configure | **Runtime Manager** | `17` |
| The immutable governance record | **Audit log** (event store, Phase 2) | emits to it; never edits it |

## 8. Cross-references

- `01` §4 steps 5–6 + step 10 — policy filter, approval checkpoint, isolation render.
- `06` — selection/allocation, the privilege grant governance guards.
- `07` — `Waiting` and terminal/teardown states a governance decision can drive.
- `14` — the approval pause mechanism `require_approval` routes into.
- `15` — the `runtime.*` events that form the immutable audit trail (INV-39).
- `17` — sandboxing, isolation, credentials, least-privilege (the configure-time
  governance enforcement).
- `nexus_core/domain/policy.py` + ADR-004 — the `Policy` model, closed `PolicyDecision`
  set, and single `ApprovalTaxonomy`.
- INV-28 (no subsystem hardcodes governance) / INV-30 (fail-closed default-deny).
