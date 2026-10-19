# Nexus v2 Email — Design Decisions

This document records the design analysis behind the Nexus v2 email system and the
decisions made while translating the reference design language into Nexus.

The two sources of truth were `prompt.txt` (the *behavioural* brief — how the
interface should **feel**) and the visual reference PNG (the *formal* brief — how
a premium surface is **composed**). This system is the synthesis of both, not a
copy of either.

---

## 1. Reverse-engineering the reference

The reference shows two white panels floating on a near-black canvas (with an
environmental warm gradient and avatar circles bleeding in from the edge). Setting
the environment aside, the **surface design language** reads as follows.

### Typography hierarchy
- A small, quiet title (~16–18px, medium weight) — *confident, not loud.*
- A signature **two-tone line**: a muted lead-in (`Vote on`) followed by an ink
  emphasis (`Community Chair`). Emphasis comes from **colour + weight contrast**,
  not size.
- Relaxed body copy in muted grey with generous line-height.
- Footer terms in the quietest grey, small.
- Type steps are **gradual**. There is no dramatic display type anywhere.

### Grid system
- Strict single column. Everything locks to one invisible left edge.
- A fixed comfortable content width with large, equal internal padding.
- Trailing affordances (chevron, radio) lock to one invisible right edge.

### Spacing rhythm
- Large, deliberate vertical gaps. Header → content → footer → action each get
  their own breathing zone.
- Repeated rows share identical spacing. Nothing is hand-tuned.
- The middle of the card is allowed to be **empty**. Whitespace is structural.

### Card structure
- White surface, large corner radius (~18px), **no visible shadow** (or a whisper).
- No outer border on the card itself — it separates from the canvas by colour and
  radius alone.
- The card is a self-contained object; one idea per card.

### Colour philosophy
- Monochrome foundation: white surface, near-black ink, a grey scale for hierarchy.
- **Near-black is the heaviest element** and it is spent on exactly one thing per
  surface: the primary action button.
- The *only* saturated colour is a single green status check — colour appears
  strictly as **meaning** (done), never as decoration.

### Visual weight
- Almost everything is light. The black CTA is the single anchor.
- Borders are reserved for genuine containers (the selectable option rows) and are
  hairline-quiet.

### Information density
- Deliberately low. Three list rows occupy a card that could hold ten.
- Comfort is prioritised over fitting more in.

### Reading flow
- Title → context → options/list → quiet terms → one action at the bottom.
- The eye is never asked to choose between competing focal points.

### CTA philosophy
- One dark, calm, full-width, gently-rounded button per surface. An optional
  leading glyph (`+`). Dependable, not shouty.

### Component hierarchy
- Header (title + one quiet icon action) → content (status rows / options) →
  supporting terms → primary action. State is shown by quiet leading marks
  (check / radio), never by loud labels.

---

## 2. Principles extracted (kept verbatim in spirit)

These came directly from the reference **and** were demanded by `prompt.txt`, so
they are the non-negotiable backbone of the Nexus system:

1. **Neutral-dominant palette.** White surfaces, ink text, grey hierarchy. Colour
   is rationed.
2. **Colour = meaning.** Semantic colour appears only on state (chips, dots,
   deltas, panels) — never as a background fill behind plain text.
3. **One focal point per email.** A single primary action carries the visual
   weight; everything else recedes.
4. **Spacing before borders.** Relationships are shown with whitespace first;
   hairlines only where a true container is needed.
5. **Two-tone text** (`muted label · ink value`) as the core hierarchy device —
   the reference's signature, applied across metrics, kv-grids, and list rows.
6. **Gradual type scale.** No dramatic jumps; emphasis through weight and colour.
7. **Whisper-soft elevation.** Shadows communicate elevation only, and barely.
8. **Generous, repeating rhythm** on an 8px base grid.

---

## 3. Ideas adapted for Nexus

The reference is a *product UI*. Nexus emails are *operational reports*. The
language was adapted, not transplanted:

- **The signature list row** (status dot · two-tone text · trailing chevron) became
  `list_row` — the workhorse for tasks, approvals queues, research items, and
  action items. It is the most direct quotation of the reference.
- **The selectable option row** (bordered, rounded, trailing radio) became
  `option_row` — used for approval choices and decision options.
- **The dark canvas** was reinterpreted as a **quiet light neutral canvas**
  (`#E9EAEC`) so the white card still reads as an elevated, premium surface, while
  staying reliable across email clients (full dark page backgrounds render
  inconsistently and read as "letters", not surfaces). The dark treatment is
  honoured instead by **dark-mode support**, where the canvas does go near-black.
- **The single black CTA** became the Nexus primary button (`#16181D`), used once
  per email. Secondary actions are outline-only, never a second solid block.
- **Metrics** (absent from the reference) were designed in the same language:
  label-over-value two-tone stats separated by hairlines, not boxed "cards", to
  avoid adding visual weight.

---

## 4. Deliberate departures (intentional changes for Nexus)

These break from both the old Nexus templates **and** a literal reading of the
reference, on purpose:

- **The per-type coloured accent bar is gone.** The previous system gave every
  email a loud coloured top bar for "personality". `prompt.txt` forbids exactly
  this ("avoid colourful interfaces", "one focal point", "colour communicates
  meaning"). Personality now comes from a single quiet **eyebrow + state chip**,
  not a colour band. *This is the biggest change from the old system.*
- **No dark code slab.** Logs/stack traces use a quiet light inset surface
  (`#F6F6F7`) with a hairline, instead of the old dark monospace block — so code
  belongs to the same calm system as everything else.
- **Metrics are not boxed.** Removing the card chrome around stats lowers visual
  weight, per the density and borders rules.
- **Restrained semantic colour.** All status colours are desaturated (calm green,
  muted amber, controlled red) so that "isolated moments of emphasis" stay quiet.
- **Subject + eyebrow do the personality work**, keeping the chrome identical
  across every template — reinforcing "every page designed by the same hand".

---

## 5. How this establishes a unique Nexus identity

Most "AI-generated" emails over-decorate: gradients, multiple accents, boxed
everything, loud headers. Nexus v2 is recognisable precisely because it does the
opposite, consistently:

- **An operator's surface, not a newsletter.** Two-tone operational lines, status
  dots, and hairline tables read like mission-control instrumentation.
- **One voice, one hand.** Identical chrome, one accent-as-meaning rule, one focal
  action — every email is unmistakably the same product.
- **Confidence through restraint.** The highest compliment, per `prompt.txt`, is
  *"nothing stands out, yet everything feels exactly right."* Nexus emails are
  built to earn it: the interface recedes, the operational picture remains.

The result should never read as a template. It should read as the work of one
designer who values clarity over decoration — applied to an AI control plane.

---

## 6. Token summary (authoritative values live in `EMAIL_DESIGN_SYSTEM.md`)

| Token | Value | Role |
|---|---|---|
| Canvas | `#E9EAEC` | Page background; the card floats on it |
| Surface | `#FFFFFF` | Card and content surface |
| Inset | `#F6F6F7` | Code, secondary grouping |
| Ink | `#16181D` | Primary text **and** primary button — the single anchor |
| Body | `#3F434B` | Paragraph text |
| Muted | `#8A8F98` | Labels, the two-tone lead-in, captions |
| Faint | `#AEB2BA` | Chevrons, the quietest meta |
| Hairline | `#E7E8EB` | Quiet borders and dividers |
| Success | `#1E7A4D` / dot `#2F9E68` | State: done / healthy |
| Warning | `#9A6206` / dot `#E0920A` | State: attention |
| Danger | `#B23B33` / dot `#DA4A41` | State: failed / risk |
| Info | `#2C5FB8` / dot `#3D78D6` | State: informational |
| Radius | card `18px` · component `10px` · button `12px` | Consistent corner family |

Every value is chosen so that colour means something, weight is spent once, and
space does the rest.
