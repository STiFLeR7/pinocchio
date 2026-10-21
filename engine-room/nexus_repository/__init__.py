"""``nexus_repository`` — the constitutional Repository Intelligence subsystem (P7, Grounding).

The **single owner of understanding repositories** (Constitution, Grounding plane; INV-02). Given a
repository root the :class:`~nexus_repository.engine.RepositoryIntelligence` engine **scans once** and
produces one immutable, facts-only :class:`~nexus_repository.profile.RepositoryProfile`: discovery,
workspace inventory, project classification, language/framework/dependency detection, build/test/CI
detection, ADR/contract/invariant discovery, package inventory, module dependency graph, coding
conventions, git snapshot, issue inventory, and repository health **signals** — grounded facts only.

It only understands repositories. It **never** reasons, plans, orchestrates, executes, validates,
recovers, reflects, evaluates policy, estimates complexity, chooses runtimes, or classifies
engineering work (each proven by an import-level guardrail). The profile contains **no
recommendations, no opinions, no strategy** — only grounded understanding, a pure function of the
tree (identical tree → identical profile → identical identity).

The scan runs once, the engine records one ``repository.profiled`` fact embedding the profile
(INV-17), and replay reconstructs the understanding **without rescanning**. Engineering Intelligence
consumes the profile (via :meth:`RepositoryProfile.as_facts`) as its Repository Understanding
grounding input; Repository Intelligence imports neither EI nor Planning. It reuses the P1 substrate
and integrates through additive composition (:func:`build_repository`).
"""

from __future__ import annotations

from nexus_repository.composition import RepositoryContext, build_repository
from nexus_repository.engine import SCANNER_VERSION, RepositoryIntelligence
from nexus_repository.events import REPOSITORY_PROFILED
from nexus_repository.persistence import (
    RepositoryRepositories,
    build_repository_repositories,
)
from nexus_repository.profile import (
    BuildProfile,
    CiProfile,
    ConstitutionalArtifacts,
    ConventionHints,
    DependencyProfile,
    DocumentationProfile,
    ExecutionHistory,
    GitSummary,
    HealthSignals,
    IssueInventory,
    ModuleGraph,
    OwnershipHints,
    PackageInventory,
    ProjectStructure,
    RepositoryProfile,
    TechnologyStack,
    TestProfile,
)
from nexus_repository.scanner import RepositorySnapshot, scan_tree

__version__ = "2.5.0"

__all__ = [
    "REPOSITORY_PROFILED",
    "SCANNER_VERSION",
    "BuildProfile",
    "CiProfile",
    "ConstitutionalArtifacts",
    "ConventionHints",
    "DependencyProfile",
    "DocumentationProfile",
    "ExecutionHistory",
    "GitSummary",
    "HealthSignals",
    "IssueInventory",
    "ModuleGraph",
    "OwnershipHints",
    "PackageInventory",
    "ProjectStructure",
    "RepositoryContext",
    "RepositoryIntelligence",
    "RepositoryProfile",
    "RepositoryRepositories",
    "RepositorySnapshot",
    "TechnologyStack",
    "TestProfile",
    "__version__",
    "build_repository",
    "build_repository_repositories",
    "scan_tree",
]
