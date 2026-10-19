"""``nexus_research`` — the Autonomous Research workflow (Capability Program 3).

A **consumer** of the Nexus control plane, not a platform extension: it composes the existing
engines into a complete research workflow and introduces no new architectural layer. Given a
research topic, the :class:`ResearchCoordinator` autonomously drives the full pipeline —

    Research Goal → Context → Knowledge → Planning → Research Work Packages → Orchestration
                  → Harness → Runtime Selection → Execution → Validation → Recovery
                  → Reflection → Knowledge → Research Brief

— using each engine's real entry point. Planning decomposes the topic (no special-case planner);
Runtime selection stays the Runtime Manager's; Validation judges every output; Recovery decides
governed continuations; Reflection surfaces reusable patterns; Knowledge persists them so a second
run's Planning improves through Knowledge consumption alone (INV-26).

Dependency direction: ``nexus_research`` sits above the integration layers it consumes
(``nexus_workflows``, ``nexus_runtime_adapters``) and every engine; it is imported by nothing. It
modifies no engine, contract, ADR, or invariant.
"""

from __future__ import annotations

from nexus_research.brief import ResearchBrief, build_brief
from nexus_research.coordinator import ResearchCoordinator
from nexus_research.recovery import RecoveryOutlook, recovery_outlook
from nexus_research.session import ResearchSession
from nexus_research.topic import (
    RESEARCH_CAPABILITY,
    RESEARCH_PHASES,
    ResearchPhase,
    ResearchTopic,
    reference_topic,
)
from nexus_research.workflow import ResearchWorkflow

__version__ = "2.5.0"

__all__ = [
    "RESEARCH_CAPABILITY",
    "RESEARCH_PHASES",
    "RecoveryOutlook",
    "ResearchBrief",
    "ResearchCoordinator",
    "ResearchPhase",
    "ResearchSession",
    "ResearchTopic",
    "ResearchWorkflow",
    "build_brief",
    "recovery_outlook",
    "reference_topic",
]
