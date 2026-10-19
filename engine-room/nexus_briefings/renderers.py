"""Renderers — turn a composed :class:`~nexus_briefings.document.Brief` into a delivery format (M4).

Three formats are supported: Markdown (for chat / archive), HTML (for email), and JSON (for
machine consumption). Every renderer is a **pure, deterministic** projection of the ``Brief`` — no
clock, no randomness — so the same brief always renders byte-for-byte identically (the platform's
INV-16 / INV-17 determinism carried through to the product surface).

The v1 ``nexus.intelligence.briefing`` renderers are coupled to the v1 database models and a live
clock; these v2 renderers are dependency-free projections of the governed ``Brief`` and reuse only
its aesthetic (health/status line, per-section blocks, findings, knowledge footer).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict

from nexus_briefings.document import Brief, BriefSectionView

SUPPORTED_FORMATS: tuple[str, ...] = ("markdown", "html", "json")


def _status(brief: Brief) -> str:
    return "PUBLISHABLE" if brief.is_publishable else "WITHHELD"


def _section_status(section: BriefSectionView) -> str:
    if section.is_present:
        return "validated"
    if section.validated:
        return "validated (no deliverable)"
    return f"withheld ({section.decision})"


def render_markdown(brief: Brief) -> str:
    """Render the brief as Markdown for chat delivery and archival."""
    icon = "✅" if brief.is_publishable else "⚠️"
    parts = [
        f"# {brief.title}",
        "",
        f"**Subject:** {brief.subject}",
        f"**Runtime:** `{brief.runtime_identity}` | **Status:** {icon} {_status(brief)}",
        "",
        "## Sections",
    ]
    for section in brief.sections:
        parts.append(f"### {section.heading} — {_section_status(section)}")
        parts.append(f"- Recovery: `{section.recovery_decision}`")
        parts.append(
            f"- Validated artifacts: {len(section.validated_artifacts)} | "
            f"Evidence: {len(section.evidence_refs)} refs"
        )
        for artifact in section.validated_artifacts:
            parts.append(f"  - `{artifact}`")
    parts.extend(["", "## Reusable Findings"])
    if brief.findings:
        parts.extend(f"- {finding}" for finding in brief.findings)
    else:
        parts.append("- _none surfaced this generation_")
    parts.extend(
        [
            "",
            "## Knowledge",
            f"- Persisted: {len(brief.knowledge_item_ids)} item(s)",
            f"- Consumed: {brief.knowledge_consumed} item(s)",
        ]
    )
    return "\n".join(parts)


def render_html(brief: Brief) -> str:
    """Render the brief as email-friendly HTML."""
    color = "#15803d" if brief.is_publishable else "#b45309"
    rows = []
    for section in brief.sections:
        artifacts = "".join(f"<li><code>{a}</code></li>" for a in section.validated_artifacts)
        rows.append(
            f'<div style="margin-bottom:16px;padding:12px;border-left:4px solid {color};'
            f'background:#f8fafc;">'
            f'<h3 style="margin:0 0 4px 0;">{section.heading} '
            f"<small>({_section_status(section)})</small></h3>"
            f'<div style="font-size:13px;color:#475569;">Recovery: {section.recovery_decision} | '
            f"Evidence: {len(section.evidence_refs)} refs</div>"
            f"<ul>{artifacts}</ul></div>"
        )
    findings = "".join(f"<li>{finding}</li>" for finding in brief.findings) or "<li>none</li>"
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{brief.title}</title></head>"
        '<body style="font-family:Helvetica,Arial,sans-serif;color:#334155;'
        'max-width:640px;margin:0 auto;">'
        f'<div style="background:#0f172a;color:#fff;padding:20px;text-align:center;">'
        f'<h2 style="margin:0;">{brief.title}</h2>'
        f'<div style="font-size:12px;color:#94a3b8;">{brief.subject}</div></div>'
        f'<div style="padding:20px;">'
        f'<div style="padding:10px;border-radius:6px;background:{color}1a;color:{color};'
        f'font-weight:bold;text-align:center;">Runtime {brief.runtime_identity} · {_status(brief)}'
        "</div>"
        f"{''.join(rows)}"
        f"<h3>Reusable Findings</h3><ul>{findings}</ul>"
        f"<h3>Knowledge</h3><p>Persisted {len(brief.knowledge_item_ids)} · "
        f"Consumed {brief.knowledge_consumed}</p>"
        "</div>"
        '<div style="background:#f8fafc;padding:12px;text-align:center;font-size:12px;'
        'color:#64748b;">Nexus Control Plane — Briefings</div>'
        "</body></html>"
    )


def render_json(brief: Brief) -> str:
    """Render the brief as canonical, deterministic JSON."""
    return json.dumps(asdict(brief), indent=2)


_RENDERERS: dict[str, Callable[[Brief], str]] = {
    "markdown": render_markdown,
    "html": render_html,
    "json": render_json,
}


def render(brief: Brief, fmt: str = "markdown") -> str:
    """Render ``brief`` in ``fmt`` (one of :data:`SUPPORTED_FORMATS`)."""
    try:
        renderer = _RENDERERS[fmt]
    except KeyError:
        raise ValueError(
            f"unsupported briefing format {fmt!r}; expected one of {SUPPORTED_FORMATS}"
        ) from None
    return renderer(brief)
