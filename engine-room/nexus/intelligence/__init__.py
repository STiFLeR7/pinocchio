"""Intelligence module for LLM routing and prompt management."""

from __future__ import annotations

from nexus.intelligence.briefing import BriefingService, BriefingType
from nexus.intelligence.openrouter import OpenRouterClient
from nexus.intelligence.research import ResearchProvider, ResearchService, RSSProvider
from nexus.intelligence.summary import SummaryEngine

__all__ = [
    "BriefingService",
    "BriefingType",
    "OpenRouterClient",
    "RSSProvider",
    "ResearchProvider",
    "ResearchService",
    "SummaryEngine",
]
