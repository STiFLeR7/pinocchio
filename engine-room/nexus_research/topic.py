"""The research topic — the immutable description of one research request.

A :class:`ResearchTopic` is *what* to research, expressed in ``nexus_core`` / engine terms only.
It names no engine, no runtime, and no plan: the four research phases it decomposes into are a
declaration of work (Planning turns them into actual Work Packages and an Execution Graph — see
:mod:`nexus_research.workflow`). Research is a consumer of the platform, so the topic introduces
no new domain concept.

The phases map onto the existing ``code_generation`` capability every runtime advertises, so the
same research Work Package is eligible on Claude, Gemini, and Shell without any adapter change
(the capability-match fact the Runtime Manager already enforces).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The abstract capability a research stage requires. It is deliberately the existing
# ``code_generation`` capability the shipped runtimes advertise — research adds no capability
# and no adapter change; a research stage is content the runtime generates.
RESEARCH_CAPABILITY = "code_generation"


@dataclass(frozen=True, slots=True)
class ResearchPhase:
    """One declared phase of a research workflow (a Planning input atom, not a plan)."""

    key: str
    objective_template: str

    def objective(self, subject: str) -> str:
        """The concrete objective for ``subject`` (still declarative — no how/where)."""
        return self.objective_template.format(subject=subject)


# The canonical research decomposition (Milestone 2). Planning — not this module — turns these
# declared phases into Work Packages; they are independent units that each produce evidence.
RESEARCH_PHASES: tuple[ResearchPhase, ...] = (
    ResearchPhase("gather-sources", "gather primary and secondary sources on {subject}"),
    ResearchPhase("summarize-evidence", "summarize the gathered evidence on {subject}"),
    ResearchPhase("compare-findings", "compare and contrast the findings on {subject}"),
    ResearchPhase("generate-briefing", "generate the technical briefing on {subject}"),
)


@dataclass(frozen=True, slots=True)
class ResearchTopic:
    """The immutable specification of one research request (subject + framing)."""

    subject: str
    question: str
    knowledge_subject: str
    corpus_key: str = "corpus"
    scope_terms: tuple[str, ...] = ()
    phases: tuple[ResearchPhase, ...] = field(default_factory=lambda: RESEARCH_PHASES)


def reference_topic() -> ResearchTopic:
    """The canonical example topic: MCP adoption → a technical briefing."""
    return ResearchTopic(
        subject="Model Context Protocol adoption",
        question="Research Model Context Protocol adoption and produce a technical briefing.",
        knowledge_subject="model context protocol adoption research",
        corpus_key="mcp-corpus",
        scope_terms=("model-context-protocol", "adoption"),
    )
