"""Repository Intelligence — the single constitutional owner of understanding repositories.

Given a repository root it **scans once** and produces one immutable, facts-only
:class:`~nexus_repository.profile.RepositoryProfile`. It only understands repositories: it never
reasons, plans, executes, validates, recovers, reflects, evaluates policy, estimates complexity,
chooses runtimes, or classifies engineering work. The profile is a **pure function of the tree** —
identical tree → identical profile → identical identity.

The scan runs once, the engine records **one** ``repository.profiled`` fact embedding the profile
(INV-17), and replay reconstructs the understanding without rescanning. Persistence rides the
P1/ADR-007 substrate through the injected infrastructure.
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventEmitter
from nexus_repository import discovery, ids
from nexus_repository.events import REPOSITORY_PROFILED, build_event, system_now
from nexus_repository.graph import module_graph, package_inventory
from nexus_repository.inventory import (
    constitutional_artifacts,
    git_summary,
    health_signals,
    issue_inventory,
)
from nexus_repository.observability import RepositoryObservability
from nexus_repository.persistence import RepositoryRepositories
from nexus_repository.profile import (
    ExecutionHistory,
    PackageInventory,
    RepositoryProfile,
)
from nexus_repository.scanner import scan_tree

SCANNER_VERSION = "1"


class RepositoryIntelligence:
    """Deterministic, facts-only repository understanding (scan once, emit once, replay forever)."""

    def __init__(
        self,
        *,
        emitter: EventEmitter | None = None,
        repositories: RepositoryRepositories | None = None,
        observability: RepositoryObservability | None = None,
        now: Callable[[], str] | None = None,
        scanner_version: str = SCANNER_VERSION,
    ) -> None:
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or RepositoryObservability()
        self._now = now or system_now
        self._version = scanner_version

    @property
    def scanner_version(self) -> str:
        """The version of the scanner (a versioned input recorded on every profile — INV-17)."""
        return self._version

    def profile(
        self,
        root: str,
        *,
        correlation_identifier: str = "",
        request_identifier: str | None = None,
        repository_history: object | None = None,
        persist: bool = True,
    ) -> RepositoryProfile:
        """Scan ``root`` into one immutable, facts-only profile (identical tree → identical profile).

        ``repository_history`` is Execution History's repository-scoped seam (P8): a read-only view
        exposing ``available`` / ``prior_executions`` that Repository Intelligence maps into its own
        execution-history seam. Duck-typed so RI takes no dependency on ``nexus_history`` and
        reconstructs no history itself — it only *consumes* the fact. Kept out of the profile
        identity (a lookup seam), so it never perturbs determinism.
        """
        history = self._history_seam(repository_history)
        snapshot = scan_tree(root)
        if not snapshot.exists:
            profile = self._finish(self._empty(root, history), correlation_identifier)
            if persist:
                self._record(profile, request_identifier=request_identifier)
            return profile

        top = set(snapshot.entries)
        evidence: list[str] = []
        py = discovery.read_pyproject(root, top, evidence)
        pkg = discovery.read_package_json(root, top, evidence)

        technology = discovery.technology(snapshot, top, py, pkg, evidence)
        dependencies = discovery.dependencies(py, pkg)
        build = discovery.build(root, top, py, pkg, evidence)
        test = discovery.test(snapshot, top, py, pkg, evidence)
        docs = discovery.documentation(root, snapshot, top, evidence)
        structure = discovery.structure(root, snapshot, top)
        ci = discovery.ci(root, top, evidence)
        conventions = discovery.conventions(root, top, py, pkg, evidence)
        ownership = discovery.ownership(root, top, evidence)
        repo_type = discovery.repository_type(technology, structure, test)

        packages = package_inventory(root)
        graph = module_graph(root, packages)
        constitutional = constitutional_artifacts(root)
        issues = issue_inventory(root)
        git = git_summary(snapshot)
        health = health_signals(root, snapshot, top, test, ci.system, ownership.codeowners)

        draft = RepositoryProfile(
            identity="",
            root=snapshot.root,
            exists=True,
            scanner_version=self._version,
            repository_type=repo_type,
            technology=technology,
            build=build,
            test=test,
            documentation=docs,
            structure=structure,
            dependencies=dependencies,
            ci=ci,
            conventions=conventions,
            ownership=ownership,
            packages=packages,
            module_graph=graph,
            constitutional=constitutional,
            issues=issues,
            git=git,
            health=health,
            execution_history=history,
            file_count=snapshot.file_count,
            files=snapshot.files,
            evidence=tuple(sorted(set(evidence))),
        )
        profile = self._finish(draft, correlation_identifier)
        if persist:
            self._record(profile, request_identifier=request_identifier)
        return profile

    # -- assembly ----------------------------------------------------------- #

    def _finish(self, draft: RepositoryProfile, correlation_identifier: str) -> RepositoryProfile:
        identity = ids.profile_id(draft.root, draft.model_dump(mode="json"))
        return draft.model_copy(
            update={
                "identity": identity,
                "correlation_identifier": correlation_identifier or identity,
                "timestamp": self._now(),
            }
        )

    @staticmethod
    def _history_seam(repository_history: object | None) -> ExecutionHistory:
        """Map Execution History's read-only seam into RI's own ``ExecutionHistory`` (duck-typed)."""
        if repository_history is None:
            return ExecutionHistory()
        return ExecutionHistory(
            available=bool(getattr(repository_history, "available", False)),
            prior_executions=int(getattr(repository_history, "prior_executions", 0)),
        )

    def _empty(self, root: str, history: ExecutionHistory) -> RepositoryProfile:
        from nexus_repository.profile import (
            BuildProfile,
            CiProfile,
            ConstitutionalArtifacts,
            ConventionHints,
            DependencyProfile,
            DocumentationProfile,
            GitSummary,
            HealthSignals,
            IssueInventory,
            ModuleGraph,
            OwnershipHints,
            ProjectStructure,
            TechnologyStack,
            TestProfile,
        )

        return RepositoryProfile(
            identity="",
            root=root,
            exists=False,
            scanner_version=self._version,
            repository_type="unknown",
            technology=TechnologyStack(
                primary_language=None, languages=(), frameworks=(), package_managers=()
            ),
            build=BuildProfile(build_system=None, build_commands=(), makefile_targets=()),
            test=TestProfile(frameworks=(), test_dirs=(), test_command=None),
            documentation=DocumentationProfile(
                readme=None, doc_dirs=(), adr_locations=(), architecture_docs=(), agent_docs=()
            ),
            structure=ProjectStructure(top_level_dirs=(), source_dirs=(), entry_points=()),
            dependencies=DependencyProfile(manifest=None, direct=(), dev=()),
            ci=CiProfile(system=None, workflows=()),
            conventions=ConventionHints(
                formatters=(),
                linters=(),
                type_checkers=(),
                line_length=None,
                editorconfig=False,
                pre_commit=False,
            ),
            ownership=OwnershipHints(codeowners=False, owners=()),
            packages=PackageInventory(packages=(), package_paths=()),
            module_graph=ModuleGraph(nodes=(), edges=()),
            constitutional=ConstitutionalArtifacts(
                adr_files=(), contract_files=(), invariant_files=()
            ),
            issues=IssueInventory(issue_templates=(), has_issue_config=False),
            git=GitSummary(is_git=False, branch=None, head_commit=None),
            health=HealthSignals(
                has_readme=False,
                has_tests=False,
                has_ci=False,
                has_lockfile=False,
                has_license=False,
                has_codeowners=False,
                file_count=0,
            ),
            execution_history=history,
            file_count=0,
            files=(),
            evidence=(),
        )

    # -- persistence + events ----------------------------------------------- #

    def _record(self, profile: RepositoryProfile, *, request_identifier: str | None = None) -> None:
        self._obs.profiled(
            repository_type=profile.repository_type,
            primary_language=profile.technology.primary_language,
            file_count=profile.file_count,
        )
        if self._repos is not None:
            self._repos.profiles.add(profile)
        if self._emitter is not None:
            self._emitter.emit(self._profiled_event(profile, request_identifier=request_identifier))

    def _profiled_event(
        self, profile: RepositoryProfile, *, request_identifier: str | None = None
    ) -> Event:
        payload = {
            "root": profile.root,
            "request": request_identifier,
            "repository_type": profile.repository_type,
            "scanner_version": profile.scanner_version,
            "file_count": profile.file_count,
            "profile": profile.model_dump(mode="json"),
        }
        return build_event(
            ids.profiled_event_id(profile.correlation_identifier, payload),
            REPOSITORY_PROFILED,
            profile.correlation_identifier,
            payload,
            self._now(),
        )
