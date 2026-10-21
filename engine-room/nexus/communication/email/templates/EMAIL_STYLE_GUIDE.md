# Nexus Email Style Guide

How Nexus emails should *sound*, *read*, and *behave*. Pairs with
`EMAIL_DESIGN_SYSTEM.md` (the visual tokens) and `EMAIL_COMPONENT_LIBRARY.md`
(the building blocks).

---

## 1. Voice & tone

Nexus speaks like a **senior operator briefing a peer**: precise, calm,
unhurried, never breathless.

| Do | Don't |
|---|---|
| "All core subsystems are nominal." | "🎉 Great news!! Everything is awesome!" |
| "Execution failed at the compile stage." | "Oops! Something went wrong 😢" |
| "Authorization needed before execution." | "ACTION REQUIRED!!! CLICK NOW" |
| State facts, then the action. | Bury the action under prose. |
| Use numbers with units and deltas. | Vague qualifiers ("a lot", "soon"). |

**Tone by type**

- *Digest / reports*: composed, executive, scannable.
- *Approval / security*: serious, unambiguous, never alarmist — clarity reduces panic.
- *Failure*: forensic and constructive (cause → recovery), never apologetic theatre.
- *Reminder*: warm, brief, singular.
- *Conversational (Q&A)*: faithful and neutral; summarise, don't editorialise.

**Person & tense.** Second person to the operator ("your control plane"),
present tense for state, past tense for events. Active voice always.

---

## 2. Writing rules

1. **Front-load the verdict.** First line = the conclusion (healthy / failed /
   needs approval). Detail follows.
2. **One idea per section.** If a section needs an "and", it's two sections.
3. **Numbers are typeset.** Wrap IDs, counts, durations, and paths in the mono
   or badge treatment so they're scannable.
4. **Deltas carry direction + semantics.** `+6 ▲` green for good, `−2 ▼` green
   when "down is good" (failures), red when "down is bad". Use the `trend`
   values `up · down · flat · up-bad · down-good`.
5. **No empty sections.** A template must hide a block when its data is absent
   (`{% if %}` guards everywhere). Never render "No data".
6. **Links are verbs.** "Review →", "Read →", "Open dashboard" — not "click here".

---

## 3. Colour usage rules

- **No decorative colour, anywhere.** There is no coloured masthead or per-type
  accent bar. The chrome is identical across every template; personality comes
  from the eyebrow and a single state chip (§6).
- **Ink is the only weight.** Near-black (`#16181D`) is the heaviest element and is
  spent once per email — on the primary button. Don't introduce a second heavy
  block.
- **Semantic colour only on state.** Green/amber/red/blue appear on chips, panels,
  dots, and deltas — never as background fills for plain text. All tones are
  desaturated so emphasis stays quiet.
- **Surfaces stay neutral.** Cards are white; the inset surface is for code and
  soft grouping. Coloured tints are reserved for `panel()`.
- **One solid action.** Primary action solid ink; secondary as `outline`/`ghost`.
  Two buttons only for a genuine pair (Approve/Reject) — and even then, only the
  primary is solid.
- **Never rely on colour alone.** Pair every state colour with a glyph or label
  (✓, ▲, "Healthy", "Medium risk") for colour-blind and grayscale readers.

---

## 4. Spacing & rhythm

- Section gutter `32px` desktop / `20px` mobile — never hand-tune per template.
- Between major sections: `divider()` (hairline + 20px each side).
- Within a section: `spacer(10–16)`.
- Cards in a list: `8–10px` gap.
- Don't crowd CTAs: at least `divider()` above a final button row.

---

## 5. Iconography rules

- Use only the approved glyph set (`EMAIL_DESIGN_SYSTEM.md` §6).
- One glyph meaning, everywhere: `→` next, `✓` done, `✕` reject, `★` importance,
  `●` insight, `▪` architecture, `☐/☑` action item, `⏰` time, `↻` retry.
- Emoji allowed sparingly and only where it adds scan-speed (`🚨` priority feed,
  `📧` email sent, `🔬` research, `🟢/🔴` liveness). Never decorative emoji in
  executive reports.

---

## 6. Personality-per-type (authoritative)

Identity is carried by the **eyebrow** (always present) and the **opening state
chip** (where a type has a natural status), not by any colour bar. The chrome is
identical everywhere. Use these tones for the opening chip:

| Template | Eyebrow | Opening chip tone |
|---|---|---|
| morning_digest | Morning Digest | health → `success`/`warning` |
| operational_intelligence | Operational Intelligence | `info` (state in metrics) |
| research_report | Research Intelligence | importance → `info` |
| todo_digest | TODO Digest | — (no chip; summary line) |
| reminder | Reminder | `info` (⏰ time) |
| approval_required | Approval Required | risk → `warning`/`danger` |
| execution_completed | Runtime Completed | `success` |
| execution_failed | Runtime Failed | `danger` |
| security_alert | Security Alert | severity → `danger`/`warning` |
| scheduler_report | Scheduler Report | health → `success`/`warning` |
| weekly_review | Weekly Operations | — (KPI metrics lead) |
| monthly_executive | Monthly Executive Report | — (highlights lead) |
| conversations/qa_transcript | Q&A Transcript | — |
| conversations/conversation_summary | Conversation Summary | — (TL;DR panel) |
| conversations/action_items | Action Items | per-item marks |
| conversations/decision_summary | Decision Summary | per-decision `status` |

---

## 7. Subject line system

**Format:** `[Nexus] <Title>` with an optional ` — <qualifier>`. Keep ≤ ~60
chars so it doesn't truncate on mobile. Sentence case. No ALL-CAPS, no emoji in
the subject itself (emoji belongs in-body). Put the most decision-relevant token
early. Preheader (`subtitle`) extends, never repeats, the subject.

**Conventions**

- Status/severity goes after an em dash: `— Healthy`, `— MEDIUM risk`, `— failed`.
- Time-boxed reports name the window: `(24h)`, `(Wk 26)`, `(June 2026)`.
- Counts when they drive the open: `3 approvals pending`.

### 50+ subject patterns

**Morning / digest**
1. `[Nexus] Morning Operational Digest`
2. `[Nexus] Morning Digest — all systems nominal`
3. `[Nexus] Morning Digest — 1 alert, 3 approvals`
4. `[Nexus] Good morning — your control plane is ready`
5. `[Nexus] Daily Briefing — {date}`

**Operational intelligence**
6. `[Nexus] Operational Intelligence Report`
7. `[Nexus] Operations — p95 latency up 12%`
8. `[Nexus] Operational Report (24h)`
9. `[Nexus] System Intelligence — degraded throughput`
10. `[Nexus] Control Plane Status — {date}`

**Research**
11. `[Nexus] Research Intelligence`
12. `[Nexus] Research — {topic}`
13. `[Nexus] High-signal research: {headline}`
14. `[Nexus] Research Briefing — 20 new findings`
15. `[Nexus] Intelligence digest — {topic}`

**TODO / productivity**
16. `[Nexus] Your TODO Digest`
17. `[Nexus] Today — 5 tasks, 1 blocked`
18. `[Nexus] TODOs — 2 due today`
19. `[Nexus] Your day, planned`

**Reminder**
20. `[Nexus] Reminder — {reason}`
21. `[Nexus] Reminder — {reason} in 30 min`
22. `[Nexus] Don't forget: {reason}`
23. `[Nexus] Heads up — {reason} at {time}`

**Approval**
24. `[Nexus] Approval Required`
25. `[Nexus] Approval Required — {task}`
26. `[Nexus] Approval Required — {risk} risk`
27. `[Nexus] Action needed — authorize {task}`
28. `[Nexus] 3 approvals awaiting you`
29. `[Nexus] Approval expires in 4h — {task}`

**Execution completed**
30. `[Nexus] Execution Completed — {task}`
31. `[Nexus] {task} finished in {duration}`
32. `[Nexus] Done — {task} (2 artifacts)`
33. `[Nexus] Task complete — {task}`

**Execution failed**
34. `[Nexus] Execution Failed — {task}`
35. `[Nexus] {task} failed at {stage}`
36. `[Nexus] Incident — {task} ({exit_status})`
37. `[Nexus] Failure — {task}, recovery suggested`

**Security**
38. `[Nexus] Security Alert — {category}`
39. `[Nexus] {severity} severity — {category} violation`
40. `[Nexus] Governance — policy triggered`
41. `[Nexus] Sandbox blocked an action`

**Scheduler**
42. `[Nexus] Scheduler Report (24h)`
43. `[Nexus] Scheduler — 1 job failed`
44. `[Nexus] Jobs summary — 18 ran, 2 skipped`

**Weekly / monthly**
45. `[Nexus] Weekly Operational Review (Wk {n})`
46. `[Nexus] Weekly Operations — {date_range}`
47. `[Nexus] Monthly Executive Report — {month}`
48. `[Nexus] {month} in review`
49. `[Nexus] Quarterly operations summary`

**Conversational / Q&A**
50. `[Nexus] Conversation Summary — {topic}`
51. `[Nexus] Session recap — {date}`
52. `[Nexus] Q&A transcript — {topic}`
53. `[Nexus] Action items from your session ({n})`
54. `[Nexus] Decision summary — {topic}`
55. `[Nexus] Follow-ups from {date}`

---

## 8. Accessibility checklist

Every template must pass before it ships:

- [ ] **Contrast** — body text ≥ 4.5:1; large/bold ≥ 3:1 (tokens in §3 comply).
- [ ] **Real text** — no text baked into images; the body is selectable & translatable.
- [ ] **Semantic structure** — one `<h1>` (header title), `<h2>` per section, `<pre>` for code.
- [ ] **`lang` set** — `<html lang="en">`; localisable.
- [ ] **Colour never alone** — every state has a glyph or label too.
- [ ] **Link text is descriptive** — "Review →", not "here".
- [ ] **Tap targets** — buttons ≥ 42px tall; full-width on mobile.
- [ ] **Preheader present** — meaningful inbox preview, not repeated subject.
- [ ] **Reading order** — single column; DOM order = visual order for screen readers.
- [ ] **Dark mode** — verified in both schemes; no invisible text.
- [ ] **Reduced clutter** — tables marked `role="presentation"` so AT doesn't announce layout tables as data.
- [ ] **alt text** — any decorative shape is empty/`role=presentation`; any future content image carries real `alt`.
