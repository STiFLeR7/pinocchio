"""Repository Intelligence value objects — the immutable, facts-only RepositoryProfile.

Repository Intelligence emits **exactly one** artifact: the :class:`RepositoryProfile` — grounded
repository understanding, **facts only** (no recommendations, no opinions, no strategy, no planning).
Every facet is a frozen :class:`~nexus_core.contracts.base.ValueObject` (value equality, serializable,
storable, durable) so the profile embeds in a ``repository.*`` event and replays without rescanning.
It is a subsystem value object (the estimation/EI/intent pattern): the ``repository_understanding``
contract is a declared void, so this freezes no new core contract (INV-07 discipline).

The whole profile is a **pure function of the repository tree** — identical tree → identical profile
→ identical identity. (``execution_history`` is a lookup *seam* into the separate Execution History
grounding subsystem, empty until it exists, so it never perturbs determinism.)
"""

from __future__ import annotations

from nexus_core.contracts.base import ValueObject


class TechnologyStack(ValueObject):
    """Detected languages, frameworks, and package managers (facts from manifests + extensions)."""

    primary_language: str | None
    languages: tuple[str, ...]
    frameworks: tuple[str, ...]
    package_managers: tuple[str, ...]


class BuildProfile(ValueObject):
    """Detected build system and commands (facts from Makefile / manifests / scripts)."""

    build_system: str | None
    build_commands: tuple[str, ...]
    makefile_targets: tuple[str, ...]


class TestProfile(ValueObject):
    """Detected test frameworks, directories, and command (facts)."""

    frameworks: tuple[str, ...]
    test_dirs: tuple[str, ...]
    test_command: str | None


class DocumentationProfile(ValueObject):
    """Discovered documentation locations, including ADRs and architecture/agent docs (facts)."""

    readme: str | None
    doc_dirs: tuple[str, ...]
    adr_locations: tuple[str, ...]
    architecture_docs: tuple[str, ...]
    agent_docs: tuple[str, ...]


class ProjectStructure(ValueObject):
    """Workspace inventory: top-level dirs, source dirs, entry points (facts)."""

    top_level_dirs: tuple[str, ...]
    source_dirs: tuple[str, ...]
    entry_points: tuple[str, ...]


class DependencyProfile(ValueObject):
    """Discovered declared dependencies (facts from the manifest)."""

    manifest: str | None
    direct: tuple[str, ...]
    dev: tuple[str, ...]


class CiProfile(ValueObject):
    """Discovered CI system and workflow files (facts)."""

    system: str | None
    workflows: tuple[str, ...]


class ConventionHints(ValueObject):
    """Extracted coding-convention facts (formatters, linters, type checkers, line length)."""

    formatters: tuple[str, ...]
    linters: tuple[str, ...]
    type_checkers: tuple[str, ...]
    line_length: int | None
    editorconfig: bool
    pre_commit: bool


class OwnershipHints(ValueObject):
    """Discovered ownership facts (CODEOWNERS presence and owners)."""

    codeowners: bool
    owners: tuple[str, ...]


class PackageInventory(ValueObject):
    """Discovered top-level Python packages (name → relative path; facts)."""

    packages: tuple[str, ...]
    package_paths: tuple[str, ...]


class ModuleGraph(ValueObject):
    """Intra-repository module dependency graph (nodes + import edges; deterministic facts).

    Nodes are top-level packages; an edge ``(a, b)`` means a module under package ``a`` imports
    package ``b`` (both intra-repo). Extracted from Python ``import`` statements via ``ast``.
    """

    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]


class ConstitutionalArtifacts(ValueObject):
    """Discovered ADR, contract, and invariant artifacts (facts — the architecture's own records)."""

    adr_files: tuple[str, ...]
    contract_files: tuple[str, ...]
    invariant_files: tuple[str, ...]


class IssueInventory(ValueObject):
    """Discovered on-disk issue-tracking facts (templates/config; no remote fetch — deterministic)."""

    issue_templates: tuple[str, ...]
    has_issue_config: bool


class GitSummary(ValueObject):
    """Deterministic git snapshot facts read from ``.git`` (no shelling out, no history walk)."""

    is_git: bool
    branch: str | None
    head_commit: str | None


class HealthSignals(ValueObject):
    """Repository health **signals** — factual presence indicators only (no grade, no opinion)."""

    has_readme: bool
    has_tests: bool
    has_ci: bool
    has_lockfile: bool
    has_license: bool
    has_codeowners: bool
    file_count: int


class ExecutionHistory(ValueObject):
    """Execution-history lookup seam — empty until the Execution History subsystem exists.

    Kept **out** of the profile's deterministic identity so repeated scans stay identical; it is a
    read-only grounding lookup, not a scan fact.
    """

    available: bool = False
    prior_executions: int = 0


class RepositoryProfile(ValueObject):
    """The single, immutable, facts-only grounding artifact Repository Intelligence produces."""

    identity: str
    root: str
    exists: bool
    scanner_version: str
    repository_type: str
    technology: TechnologyStack
    build: BuildProfile
    test: TestProfile
    documentation: DocumentationProfile
    structure: ProjectStructure
    dependencies: DependencyProfile
    ci: CiProfile
    conventions: ConventionHints
    ownership: OwnershipHints
    packages: PackageInventory
    module_graph: ModuleGraph
    constitutional: ConstitutionalArtifacts
    issues: IssueInventory
    git: GitSummary
    health: HealthSignals
    execution_history: ExecutionHistory
    file_count: int
    files: tuple[str, ...] = ()
    evidence: tuple[str, ...]
    correlation_identifier: str = ""
    timestamp: str = ""

    def as_facts(self) -> dict[str, object]:
        """A flat, read-only facts mapping for grounding consumers (e.g. Engineering Intelligence).

        Facts only — no recommendation, opinion, or strategy. Engineering Intelligence consumes this
        as its Repository Understanding input; it never inspects the repository itself.
        """
        return {
            "repository_type": self.repository_type,
            "primary_language": self.technology.primary_language,
            "languages": list(self.technology.languages),
            "frameworks": list(self.technology.frameworks),
            "package_managers": list(self.technology.package_managers),
            "build_system": self.build.build_system,
            "test_frameworks": list(self.test.frameworks),
            "test_command": self.test.test_command,
            "source_dirs": list(self.structure.source_dirs),
            "entry_points": list(self.structure.entry_points),
            "packages": list(self.packages.packages),
            "adr_files": list(self.constitutional.adr_files),
            "contract_files": list(self.constitutional.contract_files),
            "invariant_files": list(self.constitutional.invariant_files),
            "ci": self.ci.system,
            "has_tests": self.health.has_tests,
            "has_ci": self.health.has_ci,
            "file_count": self.file_count,
        }
