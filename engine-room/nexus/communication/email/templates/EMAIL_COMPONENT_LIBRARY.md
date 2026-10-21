# Nexus Email Component Library (v2)

The reusable building blocks. Compose every email from these — reach for an
existing macro before writing bespoke HTML. Each entry gives the import, signature,
an example, and notes.

> Import partials **inside** `{% block content %}` (Jinja inheritance quirk — see
> `EMAIL_TEMPLATE_GUIDELINES.md` §1):
> `{% import "partials/list_row.html" as lst %}`
> Header and footer are auto-included by `base.html`; you never import them.

---

## Layout & shell

### `base.html` — master layout
- **Blocks:** `title`, `preheader`, `content`.
- **Provides:** head, dark-mode + responsive `<style>`, canvas → card scaffold,
  header/footer includes, preheader text.
- **Use:** `{% extends "base.html" %}` then override `content` only. *(There is no
  `accent` block — personality comes from the eyebrow + a state chip.)*

### `partials/header.html` — brand lockup
- **Renders:** ink monogram tile + "Nexus" wordmark, right-aligned `timestamp`,
  `eyebrow`, `subject` (`<h1>`), `subtitle`, hairline.
- **Context:** `eyebrow, subject, subtitle, timestamp`.

### `partials/footer.html` — quiet closer
- **Renders:** `brand_links`, brand line + `version`, automation note, generated-at.
- **Context:** `brand_links, version, footer_note, timestamp`.

---

## Signature patterns — `list_row.html` → `lst`

The most Nexus-specific blocks, quoted directly from the reference.

### List row
Status mark · two-tone text (muted lead · ink subject) · trailing meta/chevron.

```jinja
{% import "partials/list_row.html" as lst %}
{{ lst.list_row("Community Chair", lead="Vote on", meta="3 candidates",
                status="done", href="#") }}
{{ lst.list_rows([
   {"subject":"Ship priority feed", "meta":"P1", "status":"pending"},
   {"subject":"Recovery check", "meta":"active", "status":"active"}
]) }}
```
- **`list_row(subject, lead=None, meta=None, status=None, href=None)`**
- **`list_rows(items)`** — items are dicts of the same params; pure-spacing list.
- **`mark(status)`** — leading indicator: `done/success`→green check,
  `pending/todo/open`→empty ring, `warning/danger/info`→dot.

### Option row
Bordered, rounded choice with a trailing radio (approval options, decisions).

```jinja
{{ lst.option_rows([
   {"label":"Joanna Sharpe", "selected":true},
   {"label":"William Lewis-Norton"}
]) }}
```
- **`option_row(label, selected=False)`**, **`option_rows(items)`**.

---

## Content components

### Section — `section.html` → `sec.section`
Quiet titled group (eyebrow + title), no coloured tick. Call form.

```jinja
{% import "partials/section.html" as sec %}
{% call sec.section("System health", eyebrow="Past 24 hours") %} ... {% endcall %}
```
- **`section(title, eyebrow=None, top=28)`**; body via `{{ caller() }}`.

### Panel — `section.html` → `sec.panel`
The only place a tint touches a block. Soft callout for TL;DR / cause / alerts.

```jinja
{% call sec.panel("warning", title="Throughput dip") %}−8% vs 7-day avg.{% endcall %}
```
- **`panel(tone='info', title=None)`** — `info·success·warning·error·neutral`.

### Code / artifact block — `section.html` → `sec.code_block`
Light monospace inset (not a dark slab) for logs, traces, file lists.

```jinja
{{ sec.code_block(incident.stderr, label="stderr") }}
```
- **`code_block(content, label=None)`** — wraps long lines; safe on mobile.

### Metric — `metric_card.html` → `mc`
Unboxed two-tone stats, hairline-separated (prefer the row).

```jinja
{% import "partials/metric_card.html" as mc %}
{{ mc.metric_row([
   {"label":"Uptime","value":"99.98%","delta":"+0.04","trend":"up"},
   {"label":"Failures","value":"1","delta":"-2","trend":"down-good"}
]) }}
```
- **`metric(label, value, delta=None, trend='flat')`**
- **`metric_row(items)`** — up to 3; stacks ≤600px.
- **trend:** `up`(green▲) `down`(red▼) `flat`(→) `up-bad`(red▲) `down-good`(green▼).

### Timeline — `timeline.html` → `tl`
Aligned dots + spacing (no heavy rail). Scheduler runs, failure stages, roadmap.

```jinja
{% import "partials/timeline.html" as tl %}
{{ tl.timeline([
   {"time":"08:00","title":"Briefing dispatched","tone":"success","body":"3 channels"},
   {"time":"10:00","title":"Research run","tone":"info"}
]) }}
```
- **`timeline(events)`** — `events=[{time?, title, body?, tone?}]`.

### Data table / kv grid / progress — `table.html` → `tbl`
```jinja
{% import "partials/table.html" as tbl %}
{{ tbl.data_table(["Job","Status","Duration"],
                  [["research","Succeeded","12s"]], ["left","left","right"]) }}
{{ tbl.kv_grid([["Runtime","nexus"],["Repository","workspace_root"]]) }}
{{ tbl.progress(72, "success", "Step budget") }}
```
- **`data_table(columns, rows, aligns=None)`** — hairline rows, muted header.
- **`kv_grid(pairs)`** — `pairs=[[label, value], ...]`.
- **`progress(pct, tone='ink', label=None)`** — clamps 0–100; bulletproof fill.

---

## Indicators & actions

### Status chip / dot — `status_chip.html` → `chip`
```jinja
{% import "partials/status_chip.html" as chip %}
{{ chip.status_chip("Healthy", "success") }}   {{ chip.dot("warning") }}
```
- **`status_chip(text, status='info')`** — `success·warning·danger·info·pending·neutral`.
- **`dot(status='info', size=8)`** — bare dot for inline use.

### Badge — `badge.html` → `bdg`
```jinja
{% import "partials/badge.html" as bdg %}
{{ bdg.badge("Governance", "brand") }}  {{ bdg.badge("CVE-2026-1", "danger", mono=True) }}
```
- **`badge(text, tone='neutral', mono=False)`** —
  `neutral·brand·success·warning·danger·info·pending`.

### Divider / spacer — `divider.html` → `rule`
```jinja
{% import "partials/divider.html" as rule %}
{{ rule.divider(24) }}   {# hairline + 24px above/below #}
{{ rule.spacer(16) }}    {# invisible gap #}
```

### Button — `button.html` → `btn`
One solid ink anchor per email; secondaries are outline/ghost. VML for Outlook.

```jinja
{% import "partials/button.html" as btn %}
{{ btn.button("Open dashboard", url, "primary") }}
{{ btn.button_row([
   {"label":"Approve","href":a,"variant":"primary"},
   {"label":"Reject","href":r,"variant":"outline"}
]) }}
```
- **`button(label, href, variant='primary', full=True, width=536)`** — variants
  `primary·outline·ghost·danger`.
- **`button_row(buttons)`** — 1 button = full width; 2 = side by side, stack ≤600px.

---

## Higher-order patterns (compositions)

| Pattern | Built from | Seen in |
|---|---|---|
| **Verdict + evidence** | state `chip` + ink subject + `kv_grid` | completed, failed, approval |
| **Operational list** | `list_rows` (mark · two-tone · meta) | digest, todo, research, artifacts |
| **Decision surface** | `chip` + `kv_grid` + `code_block` + `button_row` | approval_required |
| **Incident report** | `panel(error)` + `kv_grid` + `timeline` + `code_block` + numbered steps | execution_failed |
| **Statistics block** | `metric_row` + `progress` | operational, weekly, monthly |
| **Callout** | `panel(tone)` | TL;DR, root cause, alerts |
| **Chat bubble** | aligned table + ink/inset bubble | qa_transcript |

---

## Q&A / conversational family mapping

Four files cover the whole conversational family; the rest are **presets** (same
structure, different `eyebrow`/`subject`/emphasis):

| Requested type | Use template | Notes |
|---|---|---|
| Q&A transcript | `conversations/qa_transcript.html` | chat bubbles, operator vs Dex |
| Conversation summary | `conversations/conversation_summary.html` | TL;DR + points + decisions + actions |
| Meeting notes / Session recap / Knowledge capture / Daily digest | `conversation_summary` | change `eyebrow`; topics = agenda |
| Decision summary | `conversations/decision_summary.html` | per-decision rationale + alternatives |
| Action items / Follow-ups | `conversations/action_items.html` | checklist with owner/due/priority |

New conversational variants should reuse one of these four rather than adding files.
