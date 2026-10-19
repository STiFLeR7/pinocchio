# Nexus Email Template Guidelines

Practical rules for authoring, extending, rendering, and QA-ing Nexus email
templates. Pairs with the Design System (tokens), Style Guide (voice), and
Component Library (blocks).

---

## 1. Anatomy of a template

Every email type is a child of `base.html`:

```jinja
{% extends "base.html" %}
{% block content %}
  {% import "partials/section.html" as sec %}   {# import what you use #}
  {% import "partials/list_row.html" as lst %}
  {% import "partials/button.html" as btn %}

  {% call sec.section("System health", eyebrow="Past 24 hours") %}
    {{ lst.list_rows(tasks) }}
  {% endcall %}

  {% if actions %}
  <tr><td>{{ btn.button(actions[0].label, actions[0].href, "primary") }}</td></tr>
  {% endif %}
{% endblock %}
```

Rules:

- **Override only `content`.** There is **no `accent` block** — the chrome is
  identical for every type; personality is the eyebrow + a state chip. The shell
  owns header, footer, canvas, card, dark mode and responsiveness.
- **The content block is a sequence of `<tr>` rows** (it sits inside the card's
  content table). Wrap section macros in `<tr><td>…</td></tr>`.
- **Import inside `content`.** Top-of-file imports in a child template are not
  reliably executed by Jinja's inheritance; importing inside the block is the
  safe, tested pattern.
- **Header/footer data comes from context** (`eyebrow`, `subject`, `subtitle`,
  `timestamp`, `version`, `brand_links`) — don't render them yourself.
- **Guard every section** with `{% if data %}` so absent data produces no empty
  block. Never print "No data".
- **One solid action.** At most one `btn.button(..., "primary")` per email;
  secondaries are `outline`/`ghost`.
- **Compose, don't hand-roll.** Use Component Library macros; only drop to raw
  table HTML for a genuinely new pattern (then consider promoting it to a macro).

---

## 2. Email-client compatibility

Targets and the techniques that satisfy them:

| Client | Engine | Key constraints handled |
|---|---|---|
| Gmail (web/iOS/Android) | Blink-ish, **strips `<style>` selectors it dislikes, no `class` in some cases** | All visual styling is **inline**; `<style>` carries only media queries |
| Apple Mail (macOS/iOS) | WebKit | Full support; dark-mode media query honoured |
| Outlook (Win, 2016–2021) | **Word (mso)** | Ghost tables for the container, **VML round-rect buttons**, `mso-table-lspace/rspace`, no border-radius on Outlook (degrades to square — acceptable) |
| Outlook.com / 365 web | Blink | Inline styles; fine |
| Yahoo / Proton / Fastmail | Mixed | Table layout + inline styles cover them |

Non-negotiables baked into the system:

- **Table-based layout**, `role="presentation"`, `cellpadding=0 cellspacing=0 border=0`.
- **Inline styles** on every visual element; `<style>` only for what can't inline
  (dark mode, responsive, a few resets).
- **600px** centred container with an **mso ghost table** wrapper.
- **VML buttons** so Outlook gets real, clickable, rounded CTAs.
- **No external images / web fonts / JS** — privacy, reliability, and no
  "load images" wall.
- **`mso-hide:all`** + zero-height preheader for inbox preview.

---

## 3. Responsive guidelines

Mobile-first content in a fixed 600px shell that adapts down:

- The container is `width:600px; max-width:600px` and becomes `100%` at ≤ 600px
  (`.nx-container`).
- Side gutters shrink `32 → 22px` via `.nx-px`.
- **Multi-column rows stack**: any cell with `.nx-stack` becomes
  `display:block; width:100%` at ≤ 600px. This drives `metric_row` and
  `button_row` to vertical layout. Spacer cells (`.nx-stack-gap`, `.nx-hide-sm`)
  hide on mobile.
- Type steps down: `.nx-title 22→21`, `.nx-metric-value 26→24`.
- Buttons go full-width (`.nx-btn a { width:100% }`).
- Touch targets ≥ 44px tall.

Breakpoint: a single `@media screen and (max-width:600px)` in `base.html`.
(Outlook ignores media queries but already shows the fixed 600px desktop layout,
which is correct for it.)

---

## 4. Dark mode

- `<meta name="color-scheme">` + `<meta name="supported-color-schemes">` declare
  support; `@media (prefers-color-scheme: dark)` remaps surfaces/ink/borders.
- `[data-ogsc]` overrides cover Outlook.com's dark transform.
- Authoring rule: use the **semantic classes** (`nx-ink`, `nx-body`, `nx-muted`,
  `nx-card`, `nx-surface`, `nx-muted-surface`, `nx-border`) on elements whose
  colour must flip. Inline light colours remain the source of truth; the media
  query overrides them in dark.
- Never set a hard white background on text without a matching dark class.

---

## 5. Charts in email

Email can't run JS/canvas, and remote chart images are blocked by default. The
system therefore uses **bulletproof bar/sparkline views** built from
`tbl.progress(...)` for trends and budgets — they render everywhere, in dark
mode, with no external load.

For richer, true charts (time series, distributions):

- Render server-side to a **static image** and attach it (or inline as a `cid:`
  attachment), with descriptive `alt`.
- Reserve the slot in-template with a labelled caption (see
  `operational_intelligence.html` / `weekly_review.html`), so the layout is
  identical whether the bar view or the image is shown.
- The **PDF export** path (see §8) swaps progress bars for vector charts.

---

## 6. Template specifications

Per-type intent, required context, and components used. Full payloads in
`sample_context.json`; per-file context docs are in each template's header comment.

| # | Template | Sections (in order) | Primary components |
|---|---|---|---|
| 1 | `morning_digest` | Exec summary · metrics · health · research · tasks · approvals · scheduler · runtime · alerts · recommendations · quick actions | metric_row, event cards, data_table, panel, timeline, status_chip, button_row |
| 2 | `operational_intelligence` | Exec summary · metrics · performance(bars) · architecture · failures · recovery · recommendations · appendix | metric_row, progress, kv_grid, data_table, timeline |
| 3 | `research_report` | Headline+importance · summary · insights · sources · recommendations · actions | section, status_chip, badge, data_table, button_row |
| 4 | `todo_digest` | Today · upcoming · blocked · completed · quick links | data_table, panel, button_row |
| 5 | `reminder` | Time chip · reason · context · suggested action · CTA | status_chip, section, panel, button |
| 6 | `approval_required` | Authorization panel · risk · metadata · reason · scope · files · Approve/Reject · expiry | panel, status_chip, kv_grid, code_block, button_row |
| 7 | `execution_completed` | Result chip · metadata · metrics · artifacts · output · logs | status_chip, kv_grid, metric_row, artifact cards, code_block |
| 8 | `execution_failed` | Failure panel · metadata · timeline · root cause · logs/stack · recovery · retry | panel, kv_grid, timeline, code_block, button_row |
| 9 | `security_alert` | Violation panel · severity · details · evidence · operator actions · acknowledge | panel, status_chip, badge, kv_grid, code_block, button |
| 10 | `scheduler_report` | Health · metrics · job runs · timeline | status_chip, metric_row, data_table, timeline |
| 11 | `weekly_review` | KPIs · trends(bars) · reliability · execution · LLM usage · cost · recommendations | metric_row, progress, kv_grid |
| 12 | `monthly_executive` | Highlights · KPIs · growth(bars) · reliability · execution · research · architecture · recommendations · roadmap | metric_row, progress, kv_grid, timeline |
| Q&A | `conversations/qa_transcript` | participants · chat turns | chat bubbles, badge |
| Q&A | `conversations/conversation_summary` | TL;DR · topics · key points · decisions · action items · follow-ups · references | panel, badge, checklist, section |
| Q&A | `conversations/action_items` | summary · item cards (owner/due/priority/done) | item cards, badge, button |
| Q&A | `conversations/decision_summary` | per-decision: status · decision · rationale · alternatives | section, status_chip, badge, panel |

---

## 7. Rendering & previewing

Render any template with Jinja2 + the sample context (design-time only):

```python
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape

root = "nexus/communication/email/templates"
env = Environment(loader=FileSystemLoader(root),
                  autoescape=select_autoescape(["html"]))
ctx = json.load(open(f"{root}/sample_context.json"))
shared = ctx["_shared"]

html = env.get_template("emails/morning_digest.html").render(
    **shared, **ctx["morning_digest"])
open("preview.html", "w", encoding="utf-8").write(html)
```

Or render all 16 at once with the design-time harness (writes `previews/`):

```bash
python scripts/render_emails.py            # render every template + assert no unresolved tags
python scripts/render_emails.py morning_digest   # one template
```

- Pre-rendered HTML examples live in [`previews/`](./previews) and PNG captures of
  every template in [`previews/screenshots/`](./previews/screenshots) (plus
  `*_light.png` variants showing light/dark parity) — open them in a browser
  (toggle OS dark mode to verify both schemes).
- For client testing, paste rendered HTML into Litmus / Email on Acid, or send
  to a Gmail + Outlook + Apple Mail test inbox.
- Sanity assertion used in design QA: rendered output contains **no** `{{` or
  `{%` (all tags resolved).

---

## 8. Integration note (design-only — not wired)

This milestone deliberately does **not** modify `EmailService` or wire templates
into any service. When integration happens later, the seam is intentionally thin:

- Add a small renderer (e.g. `EmailRenderer`) that owns a Jinja2 `Environment`
  pointed at this `templates/` dir and exposes `render(template, context) -> html`.
- Producers (briefing, approval, execution, scheduler) build a **plain context
  dict** (per `sample_context.json`) and pass `(template_name, context)`.
- `EmailService.send_briefing_email(subject, text, html)` stays unchanged — it
  receives the rendered `html`; the `text` part is generated from the same
  context for the multipart/alternative fallback.
- The accent/role mapping already aligns with the **channel harness**, so the
  same context can fan out to Discord embeds later (Design System §9).

No code in this package imports services; it is safe to ship as pure assets.

---

## 9. Logo

Default is a **bulletproof CSS monogram** (navy rounded tile + white "N") — no
asset, perfect dark-mode behaviour. To upgrade to a wordmark image later:

- Host a 2× PNG/SVG on a stable CDN; swap the monogram `<td>` in
  `partials/header.html` for an `<img>` with fixed `width/height`, `alt="Nexus"`,
  and a dark-mode swap via `@media`/`[data-ogsc]`.
- Keep the monogram as the fallback for image-blocked clients.

---

## 10. Authoring QA checklist

Before a new/changed template ships:

- [ ] Extends `base.html`; overrides only `content` (no `accent` block).
- [ ] Identity is the eyebrow + opening state chip (Style Guide §6); no colour bar.
- [ ] At most one solid (`primary`) button; secondaries are `outline`/`ghost`.
- [ ] Reuses Component Library macros; no duplicated bespoke HTML.
- [ ] Every section guarded by `{% if %}`; no empty blocks.
- [ ] All visual styles inline; nothing new added to `<style>` except global needs.
- [ ] Renders with its `sample_context.json` entry — output has no unresolved tags.
- [ ] Verified in **light and dark**, **desktop and mobile** widths.
- [ ] Buttons present as VML in Outlook (uses `btn.button`/`btn.button_row`).
- [ ] Subject + preheader follow Style Guide §7 (≤ ~60 chars, non-duplicate preheader).
- [ ] Accessibility checklist (Style Guide §8) passes.
- [ ] A preview added to `previews/` and a context entry to `sample_context.json`.
