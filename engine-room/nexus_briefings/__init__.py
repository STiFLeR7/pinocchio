"""``nexus_briefings`` — the Nexus Briefings product (Product Program 1).

A **consumer** of the Nexus control plane, not a platform extension: it turns governed execution,
validated evidence, reflection, and knowledge into production-quality operational briefings, and
introduces no new architectural layer, engine, contract, ADR, or invariant. Given a brief type the
:class:`BriefingCoordinator` drives the full pipeline —

    Brief Request → Context → Knowledge → Planning → Execution → Validation → Recovery
                  → Reflection → Knowledge Update → Brief Composer → Rendered Brief

— using each engine's real entry point. Every product (Operational Digest, Research Brief,
Architecture Brief, Project Brief) is the same code path with different configuration. The
:class:`~nexus_briefings.composer.BriefComposer` composes each brief from validated artifacts,
recovery outcomes, reflection reports, and knowledge items — never from raw runtime output — and
the renderers project it to Markdown, HTML, or JSON.

Dependency direction: ``nexus_briefings`` sits above the integration layers it consumes
(``nexus_workflows``, ``nexus_runtime_adapters``) and every engine; it is imported by nothing. It
modifies no engine, contract, ADR, or invariant.
"""

from __future__ import annotations

from nexus_briefings.brieftype import (
    BRIEF_CATALOG,
    BRIEFING_CAPABILITY,
    BriefSection,
    BriefType,
    architecture_brief,
    brief_type,
    operational_digest,
    project_brief,
    research_brief,
)
from nexus_briefings.composer import BriefComposer
from nexus_briefings.coordinator import BriefingCoordinator
from nexus_briefings.document import Brief, BriefSectionView
from nexus_briefings.renderers import (
    SUPPORTED_FORMATS,
    render,
    render_html,
    render_json,
    render_markdown,
)
from nexus_briefings.session import BriefingSession
from nexus_briefings.workflow import BriefingWorkflow

__version__ = "2.5.0"

__all__ = [
    "BRIEFING_CAPABILITY",
    "BRIEF_CATALOG",
    "SUPPORTED_FORMATS",
    "Brief",
    "BriefComposer",
    "BriefSection",
    "BriefSectionView",
    "BriefType",
    "BriefingCoordinator",
    "BriefingSession",
    "BriefingWorkflow",
    "architecture_brief",
    "brief_type",
    "operational_digest",
    "project_brief",
    "render",
    "render_html",
    "render_json",
    "render_markdown",
    "research_brief",
]
