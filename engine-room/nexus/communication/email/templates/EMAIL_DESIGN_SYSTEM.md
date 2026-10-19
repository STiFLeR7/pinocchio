# Nexus Email Design System (v2)

The visual foundation for every Nexus email. This is a **quiet, operator-grade**
system: one elevated surface, near-black as the only heavy element, colour spent
only as meaning, and space doing the work borders usually do.

Read alongside `DESIGN_DECISIONS.md` (why the system looks like this),
`EMAIL_COMPONENT_LIBRARY.md` (the building blocks), `EMAIL_STYLE_GUIDE.md` (how it
should sound), and `EMAIL_TEMPLATE_GUIDELINES.md` (how to author).

> Design north star (`prompt.txt`): *"Nothing stands out, yet everything feels
> exactly right."* The interface recedes; the operational picture remains.

---

## 1. The one-surface model

Every email is a **single elevated white card** floating on a quiet neutral canvas.
There is no coloured masthead, no banner, no per-type accent bar. The card holds,
top to bottom: header → content → footer.

```
 ┌─ canvas #E9EAEC ─────────────────────────────┐
 │                                               │
 │   ┌─ card #FFFFFF · radius 18 · soft shadow ┐ │
 │   │  N  Nexus              Jun 26 · 08:00 IST│ │
 │   │  EYEBROW                                 │ │
 │   │  Title (confident, not loud)            │ │
 │   │  Subtitle                                │ │
 │   │  ───────── hairline ─────────           │ │
 │   │  content (sections, generous rhythm)     │ │
 │   │  ───────── hairline ─────────           │ │
 │   │  links · brand · version · generated-at  │ │
 │   └──────────────────────────────────────────┘ │
 └───────────────────────────────────────────────┘
```

Personality comes from the **eyebrow + a single state chip**, never from chrome.
Every template therefore shares identical structure — "designed by one hand."

---

## 2. Colour

Neutral-dominant. Colour appears **only on state** (chips, dots, deltas, panels),
never as a fill behind plain text. Near-black is the single heaviest element and is
spent once per email, on the primary button.

### 2.1 Foundation
| Token | Hex | Role |
|---|---|---|
| Canvas | `#E9EAEC` | Page background |
| Surface | `#FFFFFF` | Card / content |
| Inset | `#F6F6F7` | Code, soft grouping |
| Hairline | `#E7E8EB` | Borders, dividers |
| Hairline (soft) | `#EEEFF1` | In-table row rules |

### 2.2 Ink scale (text + the anchor)
| Token | Hex | Role |
|---|---|---|
| Ink | `#16181D` | Primary text **and** primary button |
| Body | `#3F434B` | Paragraphs |
| Muted | `#8A8F98` | Labels, two-tone lead-in, captions |
| Faint | `#AEB2BA` | Chevrons, quietest meta |

### 2.3 Semantic (desaturated — quiet emphasis)
| Meaning | Text | Dot/fill | Soft bg | Soft border |
|---|---|---|---|---|
| Success | `#1E7A4D` | `#2F9E68` | `#ECF6F0` | `#D6EBDF` |
| Warning | `#9A6206` | `#E0920A` | `#FBF3E6` | `#F1E2C6` |
| Danger | `#B23B33` | `#DA4A41` | `#FBEDEC` | `#F1D7D4` |
| Info | `#2C5FB8` | `#3D78D6` | `#EDF2FB` | `#D8E2F6` |
| Neutral/Pending | `#5A5F68` | `#8A8F98` | `#F2F3F5` | `#E7E8EB` |

**Rule:** semantic colour always pairs with a glyph or label, never colour alone.

---

## 3. Typography

System font stack (no web fonts):
`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`.
Monospace: `"SFMono-Regular", ui-monospace, Menlo, Consolas, monospace`.

Gradual scale — emphasis comes from **weight + colour**, not size jumps.

| Role | Size / line-height | Weight | Colour |
|---|---|---|---|
| Eyebrow | 11 / — (uppercase, +1.4 tracking) | 600 | Muted |
| Title (`h1`) | 22 / 30 (→21 mobile) | 600 | Ink |
| Lead paragraph | 15 / 24 | 400 | Body |
| Section title | 15 / — | 600 | Ink |
| Body | 14 / 21–23 | 400 | Body |
| Metric value | 26 / 30 (→24 mobile) | 600 | Ink |
| Caption / meta | 12 / 18–19 | 400–500 | Muted |
| Footnote | 11 / 18 | 400 | Faint |

**Two-tone line** (the signature): a muted lead-in + an ink, 600-weight subject —
e.g. *Approve* **Deploy v1.2.0**. Used in list rows, kv pairs, metrics, titles.

---

## 4. Spacing & rhythm

8px base grid. Steps: **8 · 12 · 16 · 24 · 32 · 40**.

- Card padding: `32px` desktop, `22px` mobile (`.nx-px`).
- New section: `section()` opens with `28px` top padding.
- Between major contexts: `divider(24)` (hairline + 24 each side).
- Within a group: `spacer(8–16)` or row padding `7px`.
- List rows: pure spacing, **no separators** (the reference's calm list).

Repeated content repeats identical spacing. Large gaps only signal a new context.

---

## 5. Shape, border, elevation

- **Radius family:** card `18px`, components (chips/inputs/panels/code) `10–12px`,
  buttons `12px`, badges `6px`, dots `50%`. Consistent everywhere.
- **Borders:** hairline only, and only for true containers (option rows, tables,
  panels, code). Reach for spacing first.
- **Elevation:** the card carries a whisper shadow
  (`0 1px 2px rgba(16,18,24,.04), 0 6px 24px rgba(16,18,24,.05)`); in dark mode it
  is removed. Nothing else is elevated. Objects never appear to float.

---

## 6. Iconography & glyphs

No image icons. A small, approved glyph set, sized to the typography:

`→` next · `●` insight · `▪` architecture · `✓` done · `↻` retry · `★` importance ·
`⏰` time · `›` row affordance · `·` separator.

Emoji is avoided in executive reports; allowed sparingly only where it speeds
scanning. Glyphs never outweigh text.

---

## 7. Components (summary)

Full API in `EMAIL_COMPONENT_LIBRARY.md`.

- **list_row / list_rows** — the signature: status mark · two-tone text · trailing
  meta/chevron. Tasks, approvals, research, artifacts, decisions.
- **option_row / option_rows** — bordered rounded choice with a trailing radio.
- **metric / metric_row** — unboxed two-tone stats, hairline-separated.
- **status_chip / dot** — quiet pill with a meaning-carrying dot.
- **badge** — small categorisation label.
- **section / panel / code_block** — titled group · soft tinted callout · light
  code inset.
- **timeline** — aligned dots + spacing.
- **data_table / kv_grid / progress** — hairline instrumentation.
- **button / button_row** — one solid ink anchor; outline/ghost secondaries (VML
  for Outlook).

---

## 8. Responsiveness & client support

- Fixed `600px` card → `100%` at ≤600px; gutters `32→22`.
- Multi-column (`metric_row`, `button_row`) stacks via `.nx-stack`.
- Type steps down: title `22→21`, metric `26→24`.
- Buttons go full-width; tap targets ≥44px.
- Table-based layout, `role="presentation"`, inline styles; `<style>` carries only
  resets, dark mode, and the one breakpoint.
- Outlook: mso ghost table + **VML round-rect buttons**; ignores the media query
  but shows the correct fixed desktop card.

---

## 9. Dark mode

`<meta name="color-scheme">` + `@media (prefers-color-scheme: dark)` (plus
`[data-ogsc]` for Outlook.com). Canvas → `#0E0F12`, card → `#17191E`, ink → `#F3F4F6`,
hairlines → `#2A2D34`. The ink button inverts to a light fill. Authoring rule: put
the semantic `nx-*` classes (`nx-ink`, `nx-body`, `nx-muted`, `nx-card`,
`nx-border`, `nx-inset`, `nx-hairline`) on anything whose colour must flip.

---

## 10. Accessibility

- Body contrast ≥ 4.5:1; large/bold ≥ 3:1 (tokens comply).
- Real selectable text only — never text baked into images.
- One `<h1>` (the title); sections are semantic; `<pre>` for code.
- `<html lang="en">`; colour never the only signal; descriptive link text.
- Single-column reading order; layout tables marked `role="presentation"`.

---

## 11. Placeholder data schema

Each template consumes a plain context dict; concrete examples for all 16 live in
`sample_context.json`. `_shared` carries `version`, `timestamp`, `brand_links`; each
template adds `eyebrow`, `subject`, `subtitle` plus its own payload. This schema is
the **backend interface** — it is preserved from v1 so a future `EmailRenderer`
wires in unchanged (see `EMAIL_TEMPLATE_GUIDELINES.md` §8).

---

## 12. Future surfaces

The same context dicts and the accent-as-meaning model fan out beyond email:
Discord/Slack/Teams cards (chip tone → embed colour), a web view (drop the mso/VML
fallbacks), and a PDF export (swap `progress` bars for vector charts). Nothing in
this package imports a service; it ships as pure, reusable assets.
