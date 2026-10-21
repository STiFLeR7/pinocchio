"""Brief types — the configuration-driven description of a briefing product (Milestone 2).

A :class:`BriefType` is *what* to brief, expressed in ``nexus_core`` / engine terms only. It names
no engine, no runtime, and no plan: the sections it declares are inputs to the existing Planning
engine (which turns them into Work Packages and an Execution Graph — see
:mod:`nexus_briefings.workflow`). Every supported product — Operational Digest, Research Brief,
Architecture Brief, Project Brief — is *the same code path* with different configuration; there is
no hardcoded per-type workflow.

Each section maps onto the existing ``code_generation`` capability every runtime advertises, so the
same briefing Work Package is eligible on Claude, Gemini, and Shell without any adapter change (the
capability-match fact the Runtime Manager already enforces).
"""

from __future__ import annotations

from dataclasses import dataclass

# The abstract capability a briefing section requires. It is deliberately the existing
# ``code_generation`` capability the shipped runtimes advertise — a briefing section is content the
# runtime generates, so briefings add no capability and no adapter change.
BRIEFING_CAPABILITY = "code_generation"


@dataclass(frozen=True, slots=True)
class BriefSection:
    """One declared section of a briefing (a Planning input atom, not a plan)."""

    key: str
    heading: str
    objective_template: str

    def objective(self, subject: str) -> str:
        """The concrete objective for ``subject`` (still declarative — no how/where)."""
        return self.objective_template.format(subject=subject)


@dataclass(frozen=True, slots=True)
class BriefType:
    """The immutable, configuration-driven specification of one briefing product."""

    key: str
    title: str
    subject: str
    outcome: str
    knowledge_subject: str
    sections: tuple[BriefSection, ...]
    corpus_key: str = "operations"
    scope_terms: tuple[str, ...] = ()


# --- the supported briefing catalogue (Milestone 2, all configuration) --------------------------- #


def operational_digest() -> BriefType:
    """The Morning Operational Digest — the flagship product and default brief type."""
    return BriefType(
        key="operational-digest",
        title="Morning Operational Digest",
        subject="operational state over the last cycle",
        outcome="Compile the morning operational digest from governed, validated evidence.",
        knowledge_subject="operational digest briefing",
        corpus_key="operations-corpus",
        scope_terms=("operations", "digest"),
        sections=(
            BriefSection("survey-signals", "Signals", "survey operational signals for {subject}"),
            BriefSection("summarize-health", "Health", "summarize system health for {subject}"),
            BriefSection(
                "highlight-incidents", "Incidents", "highlight notable incidents in {subject}"
            ),
            BriefSection(
                "compose-digest", "Digest", "compose the operational digest for {subject}"
            ),
        ),
    )


def research_brief() -> BriefType:
    """A Research Brief — the same phases the Autonomous Research workflow declares."""
    return BriefType(
        key="research-brief",
        title="Research Brief",
        subject="the research subject",
        outcome="Produce a technical research briefing from validated evidence.",
        knowledge_subject="research briefing",
        corpus_key="research-corpus",
        scope_terms=("research", "briefing"),
        sections=(
            BriefSection("gather-sources", "Sources", "gather primary sources on {subject}"),
            BriefSection(
                "summarize-evidence", "Evidence", "summarize the gathered evidence on {subject}"
            ),
            BriefSection(
                "compare-findings", "Findings", "compare and contrast findings on {subject}"
            ),
            BriefSection(
                "generate-briefing", "Briefing", "generate the technical briefing on {subject}"
            ),
        ),
    )


def architecture_brief() -> BriefType:
    """An Architecture Brief — component survey, decision review, and risk assessment."""
    return BriefType(
        key="architecture-brief",
        title="Architecture Brief",
        subject="the system architecture",
        outcome="Compile an architecture briefing from validated evidence.",
        knowledge_subject="architecture briefing",
        corpus_key="architecture-corpus",
        scope_terms=("architecture", "briefing"),
        sections=(
            BriefSection("survey-components", "Components", "survey the components of {subject}"),
            BriefSection("assess-decisions", "Decisions", "assess the key decisions in {subject}"),
            BriefSection("identify-risks", "Risks", "identify architectural risks in {subject}"),
            BriefSection(
                "compose-architecture", "Summary", "compose the architecture brief for {subject}"
            ),
        ),
    )


def project_brief() -> BriefType:
    """A Project Status Brief — status collection, progress assessment, and blocker surfacing."""
    return BriefType(
        key="project-brief",
        title="Project Status Brief",
        subject="the project",
        outcome="Compile a project status briefing from validated evidence.",
        knowledge_subject="project status briefing",
        corpus_key="project-corpus",
        scope_terms=("project", "status"),
        sections=(
            BriefSection("collect-status", "Status", "collect the current status of {subject}"),
            BriefSection(
                "assess-progress", "Progress", "assess progress against goals for {subject}"
            ),
            BriefSection("surface-blockers", "Blockers", "surface active blockers in {subject}"),
            BriefSection("compose-project", "Summary", "compose the project brief for {subject}"),
        ),
    )


# The supported products, keyed by type — the whole catalogue is configuration.
BRIEF_CATALOG: dict[str, BriefType] = {
    bt.key: bt
    for bt in (operational_digest(), research_brief(), architecture_brief(), project_brief())
}


def brief_type(key: str) -> BriefType:
    """Resolve a supported brief type by key (raises ``KeyError`` on an unknown product)."""
    return BRIEF_CATALOG[key]
