# Renderers (Milestone 4)

A composed `Brief` is delivery-format-agnostic. Three renderers project it to a concrete format:

| Format | Function | Use |
|---|---|---|
| `markdown` | `render_markdown` | chat delivery and archival |
| `html` | `render_html` | email delivery |
| `json` | `render_json` | machine consumption / downstream systems |

`render(brief, fmt)` dispatches by format name (`SUPPORTED_FORMATS`), raising `ValueError` on an
unknown format. `BriefingSession.render(fmt)` is the convenience entry point.

## Deterministic by construction

Every renderer is a **pure projection** of the `Brief` — no clock, no randomness, no environment.
The same brief renders byte-for-byte identically every time, carrying the platform's INV-16 /
INV-17 determinism through to the product surface
(`test_briefing_is_byte_identical_across_repeat_runs` compares the JSON render across repeat runs).
The Markdown and HTML renderers surface a publish status
(`✅ PUBLISHABLE` / `⚠️ WITHHELD`), one block per section (validated / withheld, recovery decision,
evidence count, validated artifacts), the reusable findings, and a Knowledge footer
(persisted / consumed). JSON is `json.dumps` over the dataclass — canonical and round-trippable.

## On reusing existing rendering infrastructure

The mission asks to reuse existing rendering infrastructure "where available". The v1
`nexus.intelligence.briefing` renderers were reviewed: they are coupled to the v1 SQLAlchemy models
and a live `datetime.now()`, and importing the v1 monolith into a v2 package would violate the
layering (v2 packages depend on `nexus_core` and engines, never on the v1 application). The v2
renderers are therefore standalone, dependency-free projections of the governed `Brief` — reusing
only the v1 **aesthetic** (health/status line, per-section blocks, findings, footer), not its code.
The result is deterministic where the v1 renderer was clock-dependent.
