# Nexus Operator Experience

`nexus_operator` is the **operational interface over the existing platform** — not a new engine. It
lets a human operate Nexus as a complete control plane through one coherent `OperatorSession`,
without knowing about the underlying engines. It introduces no new architectural layer, engine,
contract, ADR, or invariant; every capability consumes existing public APIs.

## What an operator can do

Through one `OperatorSession` object:

* **submit a Goal** — `submit_goal(GoalSubmission)` drives the full pipeline (Context → Knowledge →
  Planning → Orchestration → Harness → Runtime → Execution → Validation → Recovery → Reflection →
  Knowledge) and retains the outcome;
* **generate a briefing** — `generate_briefing(BriefType)` runs the existing Briefings product;
* **monitor execution** — `timeline(submission_id)` returns a unified `OperationalTimeline`
  (Milestone 2);
* **inspect** Goals, Plans, Work Packages, Runtime Sessions, Validation Reports, Recovery Plans,
  Reflection Reports, Knowledge Items, and Briefings — `explorer` (Milestone 3);
* **search** Goals, Knowledge, Briefings, and Validation Reports — `search(query)` (Milestone 4);
* **review aggregates** — `dashboard` (Milestone 5);
* **replay** any submission from its event log — `replay(submission_id)`.

## Package shape

```
nexus_operator/
  submission.py   GoalSubmission + submission_request — an operator's Goal → a WorkflowRequest (M1)
  session.py      OperatorSession — the one coherent interface (M1)
  history.py      SessionHistory + SubmissionRecord — the immutable session record (M1)
  timeline.py     TimelineCoordinator + OperationalTimeline — the unified timeline (M2)
  explorer.py     OperationalExplorer + read-only view records (M3)
  search.py       search() + SearchResults — deterministic keyword search (M4)
  dashboard.py    OperationalDashboard + build_dashboard — aggregates from persisted state (M5)
  analysis.py     internal per-node outcome correlation (shared by explorer/dashboard)
```

## A consumer, not a platform extension

`OperatorSession` contains **no** planning, execution, validation, recovery, reflection, or
knowledge logic. Submissions drive the existing `WorkflowCoordinator` / `BriefingCoordinator`; every
read (timeline, explorer, search, dashboard) is a pure projection of persisted state. The Milestone
1 primitives are exactly this thin:

* **`GoalSubmission`** — an operator's plain description (an outcome + steps); `submission_request`
  turns it into a platform `WorkflowRequest` with one Work Item per step. It declares work; the
  existing Planning engine decomposes it (INV-04).
* **`OperatorSession`** — submit, then monitor / inspect / search / aggregate through one object.
* **`SessionHistory` / `SubmissionRecord`** — the immutable record of every submission, holding the
  raw `WorkflowRun` (and, for a briefing, the composed `Brief`).
* **`TimelineCoordinator`** — projects a submission's timeline into operator phases.

## Learning accumulates across a session

The durable Knowledge repositories are threaded from one submission to the next, so Knowledge grows,
a later submission's Planning consumes it (INV-26 — through a Knowledge query, never Reflection), and
the dashboard reflects the growth. This is the existing feedback loop, now driven by the operator.
