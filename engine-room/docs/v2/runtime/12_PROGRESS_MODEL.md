# 12 — Progress Model

**Status:** design only. Defines how the Runtime Manager reports **progress** for a
running session — phases, milestones, fractional percentages, and, as a **first-class
case**, the many runtimes that cannot report a percentage at all — **runtime-
independently**, so the same model serves Claude Code, Gemini CLI, Shell, Docker,
Browser, Python, MCP, remote workers, and runtimes not yet imagined. Progress is a
supervision concern (`01` step 13), observed during lifecycle state `Running` (`07`).

---

## 1. Principles

- **Advisory / observational.** Progress is a **hint about how far along the work
  appears to be**. It is *never* authoritative and *never* a completion signal. Process
  end is the lifecycle's `Completed` (`07`/`15`); real success is Validation's verdict
  from Evidence (INV-20). **Progress never drives validation, never drives retry, never
  declares done.**
- **Runtime-independent.** RM core does not parse provider text to infer progress. Each
  runtime's notion of progress is normalized into one snapshot shape by its **Runtime
  Adapter** (`03`); provider specifics stop at that boundary.
- **Unknown is first-class.** Most runtimes cannot produce a meaningful percentage. A
  shell command, an MCP call, or a black-box container often has **no** fraction to
  report. The model represents "unknown progress" as a **normal, expected state — never
  an error** (§4). A runtime that reports no percentage is healthy, not broken.
- **Event-sourced (ADR-001).** Each progress update is a canonical `runtime.progress`
  event (`15`). The session's "latest progress" is a **projection** of that stream
  (`02` §5), not a mutable field RM owns.
- **Recorded, not decided.** A progress snapshot captures an external observation; it
  encodes no decision RM is forbidden to make.

## 2. The progress snapshot

A progress update normalizes to one small, closed shape that RM core understands without
knowing the runtime. Every field except the phase label is **optional** — because for
many runtimes only the coarsest signal exists:

| Element | Required? | Meaning |
|---|---|---|
| **phase label** | required | a coarse, human-meaningful stage of the work (e.g. `setup`, `running`, `finalizing`); always present, even when nothing else is |
| **fraction** | optional | a fractional completion estimate in the closed interval `[0.0 … 1.0]`; **absent ⇒ unknown** (§4) |
| **milestone** | optional | a named, discrete checkpoint just reached (e.g. `tests-compiled`, `page-loaded`) |
| **monotonic note** | optional | the non-regression marker (§3): records that this snapshot does not move *backward* relative to the prior one |

> The **fraction is a fraction, not a percentage field that defaults to zero.** "0.0"
> means "observed at the start"; **absence** means "no percentage is knowable." These are
> different facts and the model keeps them distinct — collapsing them would fabricate
> precision the runtime never provided.

## 3. Ordering & monotonicity

- Progress events carry the session's **monotonic sequence** (`15` §3), interleaving with
  output (`08`), heartbeats (`10`), and artifact emissions (`13`) on **one ordered
  timeline**. Replay yields the same latest-progress projection (INV-16, ADR-001).
- **Fraction should not regress.** When a fraction is present, the design expects it to
  be non-decreasing within a session/phase. If a runtime reports a *lower* fraction than
  previously, that anomaly is **recorded as data** (an explicit note / and, where it
  indicates trouble, an error in `11`) — never silently rewritten upward. The
  no-silent-correction rule applies to progress as to everything else.
- **Phases may advance; fractions may reset per phase.** A new phase label can legitimately
  restart a fraction (e.g. phase `running` 0.0 after phase `setup` 1.0). The monotonic
  expectation is *within* a phase; the phase label carries the coarse forward motion.

## 4. Unknown progress (first-class)

Unknown progress is the **common** case, designed for explicitly:

- **Representation.** Absence of a fraction *is* the representation of unknown — the
  snapshot still has a phase label, so the session is never "blank." A runtime may emit a
  string of `runtime.progress` events that only ever change the **phase label** or
  **milestone**, never the fraction; that is a complete, valid progress story.
- **Reasoning about a session with no percentage.** When the fraction is unknown, RM and
  downstream consumers reason about the session via **other signals**, not by inventing a
  number:

  | Question | Answered by (not by a fraction) |
  |---|---|
  | Is it still alive? | `runtime.heartbeat` / last-activity (`10`) — **liveness substitutes for %** |
  | Is it moving? | phase-label changes and milestones on the progress stream |
  | Is it producing? | `runtime.output` (`08`) and `runtime.artifact_emitted` (`13`) |
  | Is it stuck? | inactivity timeout (`10`) classifying prolonged silence |

- **Never an error.** A session that completes its entire life reporting *only*
  `phase=running` with no fraction is a fully normal session. RM MUST NOT treat missing
  percentage as a fault, MUST NOT synthesize a fraction to fill the gap, and MUST NOT let
  "no %" influence whether the work is considered done.

> Liveness (heartbeats, `10`) is the **first-class substitute** for percentage. A runtime
> that cannot say *how far* can still say *I am alive*; the model leans on that instead of
> fabricating a number.

## 5. How runtimes produce progress (all normalized by the adapter)

There are three production modes, and the **adapter** (`03`) is what converts each into a
normalized `runtime.progress`. RM core sees only the snapshot shape (§2) and never the
provider mechanism:

1. **Structured tool events.** Runtimes that natively emit typed progress (e.g. Claude
   Code turn/tool events, a Python script emitting typed step records, MCP progress
   notifications) → the adapter maps each native event to a snapshot, often with a
   fraction and milestones.
2. **Log scraping (adapter-side).** Runtimes that bury progress in human log lines
   (e.g. a container printing `Step 3/10`) → the **adapter** extracts and normalizes it.
   RM core does **not** scrape stdout (`08` §6) — that knowledge lives only in the adapter.
3. **None.** Runtimes that emit no progress at all (e.g. a one-shot shell command) → the
   adapter emits at most coarse phase transitions (`setup → running → finalizing`) and
   **no fraction**; the session relies on liveness (§4).

## 6. Per-runtime progress (comparison)

How each runtime typically produces progress and whether a fraction is usually available.
The production logic lives entirely in the adapter (`03`).

| Runtime | Typical source | Fraction usually available? | Falls back to |
|---|---|---|---|
| **Shell** | none (one-shot) | no | phase + liveness (`10`) |
| **Docker** | container log lines (`Step n/m`), engine events | sometimes (adapter-scraped) | phase + heartbeats |
| **Claude Code** | structured turn / tool-call events | partial (coarse, milestone-like) | phase + milestones |
| **Browser** | navigation / load / step events | sometimes (discrete milestones) | milestones + liveness |
| **Python** | typed step records the script emits | yes, when the script opts in | phase + liveness |
| **MCP** | JSON-RPC progress notifications (when supported) | sometimes | phase + liveness |
| **Remote worker** | relayed worker progress (when supported) | sometimes | heartbeats + phase |

Reading the table: the "fraction usually available?" column is mostly **no/sometimes** —
which is exactly why unknown progress is first-class (§4). The model degrades gracefully
to phase + liveness for every runtime, so a missing percentage never destabilizes
supervision.

## 7. What the progress model is *not*

- Not a completion signal — `Completed` is the lifecycle's (`07`/`15`); success is
  Validation's (INV-20). A fraction reaching `1.0` does **not** mean the work succeeded.
- Not a validation input — **progress never drives validation** or any verdict.
- Not a recovery trigger — stalls/regressions are surfaced as facts (`10`/`11`); Recovery
  decides, not the progress stream.
- Not derived by RM core from raw output — progress is produced deliberately by the
  adapter (`03`), distinct from streaming (`08`).
- Not mandatory precision — a session may run its whole life with unknown fraction.

## 8. Cross-references

`00` (overview) · `01` (supervision step 13) · `02` (session state, latest-progress
projection) · `03` (adapter normalization of progress) · `07` (Running state; `Completed`
is not progress) · `08` (streaming vs. progress separation) · `10` (heartbeats &
inactivity — the liveness substitute for %) · `11` (anomalies as typed errors) ·
`13` (artifact emission as a production signal) · `15` (`runtime.progress` event) ·
`16` (progress in telemetry) · INV-20 (completion is Evidence-based, not progress-based).
