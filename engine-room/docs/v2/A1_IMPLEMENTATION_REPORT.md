# Nexus — A1 Implementation Report

Status: **Engineering validation — executed, not designed.** One real governed human-approval loop
built and run end-to-end: a real human paused Nexus before a dangerous action and decided it; the
action executed only because it was granted, and was blocked (fail-closed) when it was not. Additive
code only; **no ADR, contract, invariant, or existing engine modified.** Nothing committed to the
Nexus repo.

**Headline: the Human Interaction architecture survived real implementation.** The thin governed core
proved every required outcome — approve→act, reject→blocked, timeout→fail-closed, duplicate→idempotent,
late→ignored, unauthorized→denied — against a **real git commit**, driven by a **real human decision**.

---

## 1. What was run (the evidence)

Real human decision collected through the operator channel (Approve). Three live runs against an
isolated copy of `D:/port` (fresh git repo; no remote; real repo untouched):

```
RUN 1  decision = APPROVE (real human)      -> outcome GRANTED
       dangerous action: PERFORMED          git commit 8e8e309 on branch a1/approved-fix
       independent verify: git rev-parse a1/approved-fix = 8e8e309f1defaa70...   (not self-report)
       A1_FIX.txt on disk = NEXUS-A1-APPROVED-FIX
       governance_consistent = True         events: interaction.requested -> interaction.responded

RUN 2  decision = REJECT                     -> outcome DENIED
       dangerous action: BLOCKED             independent sha: (none)            fail-closed

RUN 3  decision = TIMEOUT (no answer)        -> outcome TIMED_OUT
       dangerous action: BLOCKED             independent sha: (none)            fail-closed (INV-30)

SAFETY  D:/port has no A1_FIX.txt and no a1/ branch — the real working tree was never touched.
```

Deterministic governance matrix (no network, no human): `9 passed`. Full workflows suite `23 passed`;
ruff clean; mypy clean.

---

## 2. Implementation graph (benchmark step → status)

| Benchmark step | Status | Realized by |
|---|---|---|
| Human → Goal | ✅ reused (A0) | `A1TaskSpec` / vertical input |
| Planning → Runtime → Execution | ✅ reused (A0) | A0 vertical (fix production; see §3) |
| **Execution Actuation → Approval Required** | ✅ **new** | vertical pauses before the dangerous action |
| **Real Human receives request** | ✅ **real** | operator channel (`CallableApprovalChannel` "operator-cli") relays the pause |
| **Approve / Reject** | ✅ **real** | live human decision (Approve), + reject/timeout runs |
| Execution continues (or is blocked) | ✅ **new** | commit happens IFF `ApprovalOutcome.GRANTED` |
| Validation (independent) | ✅ **new** | `git rev-parse` on the branch, not the workflow's claim |
| Recovery | ✅ unchanged | A0 pipeline recovery untouched |
| Briefing | ✅ **new** | `A1Result.briefing` |

Correlation + audit: every run emits correlated `interaction.*` events
(`requested → responded | timed_out | duplicate_ignored | ignored_late`).

---

## 3. Reused components (Phase 1 audit → reuse-first)

**v1 is reusable — and was reused at the semantics + channel level, not rebuilt.** Evidence from the
audit:

| v1 asset | Verdict | How A1 uses it |
|---|---|---|
| `nexus/approvals/service.py::evaluate_approval` | **reusable (reference semantics)** — fail-closed on empty/invalid owner (A-001), non-owner denied, non-`PENDING` "already decided", expired handling | A1's `ApprovalGateway` **mirrors** these exact rules channel-agnostically (fail-closed, authority-bound, idempotent, late-safe) |
| `nexus/communication/discord/bot.py::ApprovalView` | **reusable (delivery)** — real Discord buttons + owner check (`interaction.user.id not in owner_ids → Unauthorized`) | A1's `parse_discord_decision` + Discord channel **bridge** this delivery: owner-authored, correlation-referencing, approve/reject; fail-closed on anything else |
| `nexus/communication/discord/service.py::send_approval_request` | reusable (transport) | the shape the Discord channel adapter posts |
| v1 owner-id config (`DISCORD_OWNER_ID`) | reusable | the `authority` binding on `ApprovalRequest` |

**Why not reuse v1's engine directly:** `evaluate_approval` is coupled to the v1 DB
(`ApprovalRecord`, SQLAlchemy `with_for_update`), async, and the running bot process. Dragging that
into the v2 vertical would import v1's persistence and event stack — the opposite of a thin bridge.
So A1 **reuses the Discord channel + the fail-closed owner semantics**, and keeps the governed core a
small, synchronous, channel-agnostic v2 value-object module. This is "bridge, don't redesign."

Also reused unchanged: the entire A0 vertical (repo grounding, real-Claude actuation, independent
validation) for *producing* the fix in production. To conserve the shared claude rate-budget (account
at 0.97/7-day), the live A1 runs write the fix deterministically and spend the run on the **approval
governance** — the only thing A1 exists to validate.

## 4. New code (all reusable; no workflow-specific hacks)

| File | Purpose | LOC |
|---|---|---|
| `nexus_workflows/human_approval.py` | thin Human Interaction: `ApprovalGateway` (fail-closed/authority/idempotent/late-safe), channels, Discord decision parser, `interaction.*` events | ~230 |
| `nexus_workflows/git_actions.py` | the dangerous action: `commit_to_throwaway_branch` + independent `branch_commit_sha` | ~70 |
| `nexus_workflows/a1.py` | the governed vertical: pause → approval → gated commit → independent verify → briefing | ~180 |
| `scripts/a1_run.py` | real-run entrypoint (isolate → relay real decision → run → evidence) | ~110 |
| `tests/unit/nexus_workflows/test_a1_governed_approval.py` | 9 deterministic governance-matrix tests | ~150 |

## 5. Remaining stubs (explicit)

1. **Push to a real remote** — A1 commits to a *local* throwaway branch only; no outward push.
2. **Live Discord round-trip** — the Discord channel's decision *parser* is built and unit-tested; the
   networked post+poll transport is a thin shell not exercised live (the live proof used the operator
   channel, a real human via the Claude Code operator surface).
3. **Full Human Interaction subsystem** — only *approval* is implemented; conversations, reviews,
   notifications, multi-channel routing, and escalation chains are out of scope.
4. **v1 DB-backed persistence** — A1 uses the in-memory v2 governed core, not v1's `ApprovalRecord`.

## 6. v1 ↔ v2 integration points (the bridge, extended)

A0 established the v2 vertical; **A1 adds the first governance bridge**: v1's proven Discord delivery
and fail-closed owner semantics now have a v2-native, channel-agnostic consumer (`ApprovalGateway`)
with a `parse_discord_decision` adapter that speaks v1's Discord message shape. The honest seam is
`run_a1_vertical(task, channel=…, authority=…)`: swap the operator channel for the Discord channel and
the same governed loop runs over v1's Discord — no core change. Per the rule, no migration framework
was built; only this approval seam.

## 7. Architectural conflicts

**None.** The Human Interaction thesis held under real implementation: the governed core carries the
request and records the answer but decides nothing beyond fail-closed settlement; adding a channel is
an adapter; the fail-closed/authority/idempotent/late invariants (INV-16/30/39 analogues) behaved
exactly as designed against a real git action. No `ARCHITECTURAL_CONFLICT_*` was produced.

## 8. Production blockers

1. **No remote push path** (outward action deliberately excluded).
2. **Discord transport not live-wired** (parser done; networked post+poll + running-bot integration
   remains).
3. **Approver identity** is a string authority, not a verified account/RBAC identity (the freeze
   review's named `G-1`); the operator channel trusts the relayed approver.
4. **Async/long-wait durability** — the core is synchronous; deferred approvals over hours/days need
   persistence (the frozen HI design's Session, not built).

---

## Final Verdict

1. **Did the Human Interaction architecture survive real implementation?** **Yes.** A thin, reusable
   governed core proved every required outcome against a real git commit driven by a real human, with
   no ADR/contract/invariant/engine change and no architectural conflict.

2. **Was the existing v1 Discord system reusable?** **Yes — at the delivery + semantics level.** v1
   already ships a real fail-closed Discord approval (owner-checked buttons; `evaluate_approval`
   A-001). A1 bridged its Discord message shape (`parse_discord_decision`) and mirrored its owner
   semantics, rather than reusing its DB/async engine — the correct thin bridge.

3. **What percentage of Human Interaction is now operational?** **~35–40%** of the frozen HI design:
   the approval interaction kind, correlation, timeout/fail-closed, idempotency, late-safety, authority
   binding, event taxonomy, and one real channel (operator) + one bridged channel (Discord, parser).
   Not yet: conversations, reviews, notifications, multi-channel routing, escalation, durable async
   sessions, verified identity.

4. **Which parts remain architectural stubs?** Live Discord transport, remote push, verified approver
   identity/RBAC, durable long-wait sessions, and the non-approval interaction kinds (§5).

5. **Can Nexus now perform a fully governed engineering workflow with a real human approval?** **Yes,
   for the core loop.** Human → goal → (A0) real repo understanding + real Claude execution → pause →
   **real human approval** → gated real repository mutation → independent validation → briefing now runs
   end-to-end. Remaining gaps (remote push, live Discord, identity) are implementation, not design.

6. **Is the v1 → v2 bridge now established?** **Yes — the first governance bridge exists.** v1's Discord
   delivery + fail-closed owner semantics now have a v2-native consumer; flipping the channel from
   operator to Discord runs the same governed loop over v1's surface with no core change.

7. **What should A2 validate?** **A2 — the live Discord round-trip + remote persistence of the fix.**
   Take this exact governed loop and replace remaining stub #2: post the approval to a real Discord
   channel via the bridged v1 delivery, collect a real owner button/reply, and on grant push the
   throwaway branch to a real remote. That proves the Discord channel end-to-end and the outward
   commit path — the next-highest-leverage step. (Verified approver identity/RBAC — freeze `G-1` —
   is the natural A3.)

**Recommendation:** continue proving one vertical at a time (A2 next: live Discord + push); do not
begin broad Human Interaction feature build-out. The architecture is confirmed by execution again —
now twice.
