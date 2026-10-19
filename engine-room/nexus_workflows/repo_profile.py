"""Repository Profile -- deterministic grounding for downstream engines (A2).

This is the thin Repository Intelligence capability: given an *arbitrary, unfamiliar* repository, it
produces one deterministic :class:`RepositoryProfile` (type, stack, build, test, docs, structure,
dependencies, CI, conventions, ownership) purely from **evidence on disk** -- manifests, config
files, CI dirs, doc locations. No embeddings, no semantic search, no memory, no RAG. Same repo in →
same profile out.

Its responsibility ends at the profile (the A2 critical rule): it is grounding, not Planning,
Knowledge, Context Engineering, or search. Two seams hand the profile to existing engines with **no
engine change**: :func:`profile_to_context_fragments` (Context Engineering) and
:func:`profile_to_assumptions` (Planning's ``PlanningRequest.assumptions``). It reuses A0's
:func:`nexus_workflows.repo_intelligence.read_repository` for the file-walk substrate.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass

from nexus_context import ContextCategory, ContextSource, RawContextFragment
from nexus_workflows.repo_intelligence import RepositorySnapshot, read_repository

_IGNORE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "dist",
        "build",
        ".next",
        "coverage",
        "__pycache__",
        ".venv",
        ".ruff_cache",
    }
)

# Dependency name -> framework label (evidence-based; only well-known, unambiguous signals).
_JS_FRAMEWORKS = {
    "next": "Next.js",
    "react": "React",
    "react-dom": "React",
    "vue": "Vue",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "express": "Express",
    "@nestjs/core": "NestJS",
    "vite": "Vite",
    "electron": "Electron",
}
_PY_FRAMEWORKS = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "pydantic": "Pydantic",
    "sqlalchemy": "SQLAlchemy",
    "discord.py": "discord.py",
    "discord": "discord.py",
    "click": "Click",
    "typer": "Typer",
}
_ENTRY_CANDIDATES = (
    "__main__.py",
    "main.py",
    "manage.py",
    "app.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "Dockerfile",
)


@dataclass(frozen=True, slots=True)
class TechnologyStack:
    primary_language: str | None
    languages: tuple[str, ...]
    frameworks: tuple[str, ...]
    package_managers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BuildProfile:
    build_system: str | None
    build_commands: tuple[str, ...]
    makefile_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TestProfile:
    frameworks: tuple[str, ...]
    test_dirs: tuple[str, ...]
    test_command: str | None


@dataclass(frozen=True, slots=True)
class DocumentationProfile:
    readme: str | None
    doc_dirs: tuple[str, ...]
    adr_locations: tuple[str, ...]
    architecture_docs: tuple[str, ...]
    agent_docs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectStructure:
    top_level_dirs: tuple[str, ...]
    source_dirs: tuple[str, ...]
    entry_points: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependencyProfile:
    manifest: str | None
    direct: tuple[str, ...]
    dev: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CiProfile:
    system: str | None
    workflows: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConventionHints:
    formatters: tuple[str, ...]
    linters: tuple[str, ...]
    type_checkers: tuple[str, ...]
    line_length: int | None
    editorconfig: bool
    pre_commit: bool


@dataclass(frozen=True, slots=True)
class OwnershipHints:
    codeowners: bool
    owners: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepositoryProfile:
    """The single canonical, deterministic grounding artifact Repository Intelligence produces."""

    root: str
    exists: bool
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
    file_count: int
    evidence: tuple[str, ...]


# --------------------------------------------------------------------------- #
# Profiling
# --------------------------------------------------------------------------- #


def profile_repository(root: str) -> RepositoryProfile:
    """Produce a deterministic :class:`RepositoryProfile` for ``root`` from on-disk evidence."""
    snapshot = read_repository(root)
    if not snapshot.exists:
        return _empty_profile(root)

    top = set(snapshot.entries)
    evidence: list[str] = []
    py = _read_pyproject(root, top, evidence)
    pkg = _read_package_json(root, top, evidence)

    technology = _technology(snapshot, top, py, pkg, evidence)
    dependencies = _dependencies(py, pkg)
    build = _build(root, top, py, pkg, evidence)
    test = _test(snapshot, top, py, pkg, evidence)
    documentation = _documentation(root, snapshot, top, evidence)
    structure = _structure(root, snapshot, top)
    ci = _ci(root, top, evidence)
    conventions = _conventions(root, top, py, pkg, evidence)
    ownership = _ownership(root, top, evidence)
    repo_type = _repository_type(technology, structure, test)

    return RepositoryProfile(
        root=snapshot.root,
        exists=True,
        repository_type=repo_type,
        technology=technology,
        build=build,
        test=test,
        documentation=documentation,
        structure=structure,
        dependencies=dependencies,
        ci=ci,
        conventions=conventions,
        ownership=ownership,
        file_count=snapshot.file_count,
        evidence=tuple(sorted(set(evidence))),
    )


def _read_pyproject(root: str, top: set[str], evidence: list[str]) -> dict[str, object]:
    if "pyproject.toml" not in top:
        return {}
    try:
        with open(os.path.join(root, "pyproject.toml"), "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    evidence.append("pyproject.toml")
    return data


def _read_package_json(root: str, top: set[str], evidence: list[str]) -> dict[str, object]:
    if "package.json" not in top:
        return {}
    try:
        with open(os.path.join(root, "package.json"), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    evidence.append("package.json")
    return data if isinstance(data, dict) else {}


def _technology(
    snapshot: RepositorySnapshot,
    top: set[str],
    py: dict[str, object],
    pkg: dict[str, object],
    evidence: list[str],
) -> TechnologyStack:
    frameworks: set[str] = set()
    for name in _dep_names(pkg.get("dependencies")) + _dep_names(pkg.get("devDependencies")):
        if name in _JS_FRAMEWORKS:
            frameworks.add(_JS_FRAMEWORKS[name])
    for name in _py_dependency_names(py):
        if name in _PY_FRAMEWORKS:
            frameworks.add(_PY_FRAMEWORKS[name])

    managers: list[str] = []
    for lockfile, manager in (
        ("uv.lock", "uv"),
        ("poetry.lock", "poetry"),
        ("requirements.txt", "pip"),
        ("package-lock.json", "npm"),
        ("yarn.lock", "yarn"),
        ("pnpm-lock.yaml", "pnpm"),
        ("Cargo.lock", "cargo"),
        ("go.sum", "go modules"),
    ):
        if lockfile in top:
            managers.append(manager)
            evidence.append(lockfile)

    primary = snapshot.languages[0] if snapshot.languages else None
    # Prefer python/typescript as primary when a manifest declares them (more meaningful than 'json').
    if "pyproject.toml" in top or "setup.py" in top:
        primary = "python"
    elif "tsconfig.json" in top:
        primary = "typescript"
    elif pkg:
        primary = "javascript"
    return TechnologyStack(
        primary_language=primary,
        languages=snapshot.languages,
        frameworks=tuple(sorted(frameworks)),
        package_managers=tuple(managers),
    )


def _dependencies(py: dict[str, object], pkg: dict[str, object]) -> DependencyProfile:
    if pkg:
        return DependencyProfile(
            manifest="package.json",
            direct=tuple(sorted(_dep_names(pkg.get("dependencies")))),
            dev=tuple(sorted(_dep_names(pkg.get("devDependencies")))),
        )
    if py:
        return DependencyProfile(
            manifest="pyproject.toml",
            direct=tuple(sorted(_py_dependency_names(py))),
            dev=tuple(sorted(_py_optional_names(py))),
        )
    return DependencyProfile(manifest=None, direct=(), dev=())


def _build(
    root: str, top: set[str], py: dict[str, object], pkg: dict[str, object], evidence: list[str]
) -> BuildProfile:
    system: str | None = None
    commands: list[str] = []
    makefile_targets: list[str] = []
    if "Makefile" in top or "makefile" in top:
        system = "make"
        makefile_targets = _makefile_targets(root, top, evidence)
    scripts = pkg.get("scripts")
    if isinstance(scripts, dict):
        for key in ("build", "start", "dev", "compile"):
            if key in scripts:
                commands.append(f"npm run {key}")
        if system is None:
            system = "npm scripts"
    if not system and py:
        backend = _pyproject_build_backend(py)
        if backend:
            system = backend
            evidence.append("pyproject.toml")
    return BuildProfile(
        build_system=system,
        build_commands=tuple(commands),
        makefile_targets=tuple(makefile_targets),
    )


def _test(
    snapshot: RepositorySnapshot,
    top: set[str],
    py: dict[str, object],
    pkg: dict[str, object],
    evidence: list[str],
) -> TestProfile:
    frameworks: list[str] = []
    command: str | None = None
    dev = set(_dep_names(pkg.get("devDependencies")))
    if "jest" in dev:
        frameworks.append("jest")
    if "vitest" in dev:
        frameworks.append("vitest")
    if "@playwright/test" in dev or "playwright" in dev:
        frameworks.append("playwright")
    py_names = set(_py_dependency_names(py)) | set(_py_optional_names(py))
    if "pytest" in py_names or _has_pytest_config(py) or "pytest.ini" in top:
        frameworks.append("pytest")
        command = "pytest"
    test_dirs = tuple(d for d in ("tests", "test", "__tests__", "spec") if d in snapshot.entries)
    scripts = pkg.get("scripts")
    if isinstance(scripts, dict) and "test" in scripts:
        command = "npm test"
    if frameworks:
        evidence.append("pyproject.toml" if "pytest" in frameworks and py else "package.json")
    return TestProfile(frameworks=tuple(frameworks), test_dirs=test_dirs, test_command=command)


def _documentation(
    root: str, snapshot: RepositorySnapshot, top: set[str], evidence: list[str]
) -> DocumentationProfile:
    readme = next((d for d in snapshot.entries if d.lower().startswith("readme")), None)
    if readme:
        evidence.append(readme)
    doc_dirs = tuple(d for d in ("docs", "doc", "documentation") if d in top)
    adr = tuple(
        loc
        for loc in ("adr", "docs/adr", "docs/adrs", "doc/adr")
        if os.path.isdir(os.path.join(root, *loc.split("/")))
    )
    architecture = tuple(
        d
        for d in snapshot.entries
        if d.lower().startswith("architecture") or d.lower() in ("contracts",)
    )
    agent_docs = tuple(
        d for d in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules") if d in top
    )
    evidence.extend(agent_docs)
    return DocumentationProfile(
        readme=readme,
        doc_dirs=doc_dirs,
        adr_locations=adr,
        architecture_docs=architecture,
        agent_docs=agent_docs,
    )


def _structure(root: str, snapshot: RepositorySnapshot, top: set[str]) -> ProjectStructure:
    dirs = tuple(sorted(d for d in snapshot.entries if os.path.isdir(os.path.join(root, d))))
    source_dirs = tuple(
        d for d in ("src", "app", "lib", "pkg", "internal", "components") if d in top
    )
    entry_points = tuple(
        sorted(e for e in _ENTRY_CANDIDATES if os.path.exists(os.path.join(root, e)))
    )
    return ProjectStructure(top_level_dirs=dirs, source_dirs=source_dirs, entry_points=entry_points)


def _ci(root: str, top: set[str], evidence: list[str]) -> CiProfile:
    workflows_dir = os.path.join(root, ".github", "workflows")
    if os.path.isdir(workflows_dir):
        files = tuple(sorted(f for f in os.listdir(workflows_dir) if f.endswith((".yml", ".yaml"))))
        if files:
            evidence.append(".github/workflows")
            return CiProfile(system="github-actions", workflows=files)
    for name, system in (
        (".gitlab-ci.yml", "gitlab-ci"),
        ("azure-pipelines.yml", "azure-pipelines"),
    ):
        if name in top:
            evidence.append(name)
            return CiProfile(system=system, workflows=(name,))
    if os.path.isdir(os.path.join(root, ".circleci")):
        return CiProfile(system="circleci", workflows=("config.yml",))
    return CiProfile(system=None, workflows=())


def _conventions(
    root: str,
    top: set[str],
    py: dict[str, object],
    pkg: dict[str, object],
    evidence: list[str],
) -> ConventionHints:
    formatters: list[str] = []
    linters: list[str] = []
    type_checkers: list[str] = []
    dev = set(_dep_names(pkg.get("devDependencies")))
    if "ruff.toml" in top or ".ruff.toml" in top or _pyproject_has_tool(py, "ruff"):
        linters.append("ruff")
        formatters.append("ruff format")
    if _pyproject_has_tool(py, "black"):
        formatters.append("black")
    if "eslint" in dev or any(
        e in top for e in (".eslintrc", ".eslintrc.json", ".eslintrc.js", "eslint.config.mjs")
    ):
        linters.append("eslint")
    if "prettier" in dev or any(
        e in top for e in (".prettierrc", ".prettierrc.json", "prettier.config.js")
    ):
        formatters.append("prettier")
    if _pyproject_has_tool(py, "mypy") or "mypy.ini" in top:
        type_checkers.append("mypy")
    if "tsconfig.json" in top:
        type_checkers.append("typescript")
    line_length = _pyproject_line_length(py)
    pre_commit = ".pre-commit-config.yaml" in top
    if pre_commit:
        evidence.append(".pre-commit-config.yaml")
    return ConventionHints(
        formatters=tuple(dict.fromkeys(formatters)),
        linters=tuple(dict.fromkeys(linters)),
        type_checkers=tuple(dict.fromkeys(type_checkers)),
        line_length=line_length,
        editorconfig=".editorconfig" in top,
        pre_commit=pre_commit,
    )


def _ownership(root: str, top: set[str], evidence: list[str]) -> OwnershipHints:
    for loc in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
        path = os.path.join(root, *loc.split("/"))
        if os.path.isfile(path):
            evidence.append(loc)
            owners = _read_codeowners(path)
            return OwnershipHints(codeowners=True, owners=owners)
    return OwnershipHints(codeowners=False, owners=())


def _repository_type(
    technology: TechnologyStack, structure: ProjectStructure, test: TestProfile
) -> str:
    lang = technology.primary_language or "unknown"
    if "Next.js" in technology.frameworks:
        return "nextjs-web-app"
    if technology.frameworks:
        return f"{lang}-app ({'/'.join(technology.frameworks).lower()})"
    if lang == "python" and structure.source_dirs:
        return "python-application"
    if lang == "python":
        return "python-library"
    if lang in ("javascript", "typescript"):
        return f"{lang}-project"
    return f"{lang}-repository"


# --------------------------------------------------------------------------- #
# Deterministic queries (Phase 4 -- evidence-backed grounding answers)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RepoAnswer:
    question: str
    answer: str
    evidence: tuple[str, ...]
    confidence: str  # "high" | "medium" | "low"


def how_is_it_built(profile: RepositoryProfile) -> RepoAnswer:
    cmds = list(profile.build.build_commands) or list(profile.build.makefile_targets[:5])
    answer = f"build system: {profile.build.build_system or 'unknown'}"
    if cmds:
        answer += f"; commands: {', '.join(cmds)}"
    return RepoAnswer(
        question="How is this project built?",
        answer=answer,
        evidence=profile.evidence,
        confidence="high" if profile.build.build_system else "low",
    )


def relevant_tests(profile: RepositoryProfile, *, hint: str = "") -> RepoAnswer:
    fw = ", ".join(profile.test.frameworks) or "none detected"
    dirs = ", ".join(profile.test.test_dirs) or "no dedicated test dir"
    answer = (
        f"framework: {fw}; test dirs: {dirs}; command: {profile.test.test_command or 'unknown'}"
    )
    if hint:
        answer += f"; for '{hint}', look under {dirs} for matching names"
    return RepoAnswer(
        question="Which tests are likely relevant?",
        answer=answer,
        evidence=tuple(profile.test.test_dirs),
        confidence="high" if profile.test.frameworks else "low",
    )


def docs_to_consult(profile: RepositoryProfile) -> RepoAnswer:
    ordered: list[str] = []
    ordered.extend(
        profile.documentation.agent_docs
    )  # CLAUDE.md/AGENTS.md first — intent/conventions
    if profile.documentation.readme:
        ordered.append(profile.documentation.readme)
    ordered.extend(profile.documentation.architecture_docs)
    ordered.extend(profile.documentation.adr_locations)
    ordered.extend(profile.documentation.doc_dirs)
    return RepoAnswer(
        question="Which documentation should be consulted first?",
        answer=" > ".join(ordered) if ordered else "no documentation sources found",
        evidence=tuple(ordered),
        confidence="high" if ordered else "low",
    )


def where_to_fix(profile: RepositoryProfile, symptom: str, *, max_hits: int = 8) -> RepoAnswer:
    """Heuristically locate where a bug likely lives: files whose path matches the symptom tokens."""
    tokens = [t.lower() for t in symptom.replace("/", " ").replace("_", " ").split() if len(t) > 2]
    hits: list[str] = []
    if profile.exists and tokens:
        for current, dirnames, filenames in os.walk(profile.root):
            dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
            rel = os.path.relpath(current, profile.root)
            for name in sorted(filenames):
                path = os.path.join(rel, name) if rel != "." else name
                if any(token in path.lower() for token in tokens):
                    hits.append(path.replace("\\", "/"))
                    if len(hits) >= max_hits:
                        break
            if len(hits) >= max_hits:
                break
    if hits:
        return RepoAnswer(
            question=f"Where should '{symptom}' probably be fixed?",
            answer="candidate files: " + ", ".join(hits),
            evidence=tuple(hits),
            confidence="medium",
        )
    fallback = (
        ", ".join(profile.structure.source_dirs or profile.structure.entry_points) or "repo root"
    )
    return RepoAnswer(
        question=f"Where should '{symptom}' probably be fixed?",
        answer=f"no direct name match; start in primary source: {fallback}",
        evidence=tuple(profile.structure.source_dirs),
        confidence="low",
    )


# --------------------------------------------------------------------------- #
# Integration seams (no engine change)
# --------------------------------------------------------------------------- #


def profile_to_context_fragments(profile: RepositoryProfile) -> tuple[RawContextFragment, ...]:
    """Project the profile onto WORKSPACE + DOMAIN context fragments Context Engineering normalizes."""
    workspace = RawContextFragment(
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        key="repository_profile",
        payload={
            "repository_type": profile.repository_type,
            "primary_language": profile.technology.primary_language,
            "frameworks": list(profile.technology.frameworks),
            "package_managers": list(profile.technology.package_managers),
            "build_system": profile.build.build_system,
            "test_frameworks": list(profile.test.frameworks),
            "test_command": profile.test.test_command,
            "source_dirs": list(profile.structure.source_dirs),
            "entry_points": list(profile.structure.entry_points),
            "ci": profile.ci.system,
            "evidence": list(profile.evidence),
        },
    )
    conventions = RawContextFragment(
        source=ContextSource.WORKSPACE,
        category=ContextCategory.CONSTRAINT,
        key="repository_conventions",
        payload={
            "formatters": list(profile.conventions.formatters),
            "linters": list(profile.conventions.linters),
            "type_checkers": list(profile.conventions.type_checkers),
            "line_length": profile.conventions.line_length,
        },
    )
    return (workspace, conventions)


def profile_to_assumptions(profile: RepositoryProfile) -> tuple[str, ...]:
    """Deterministic assumption strings Planning consumes via ``PlanningRequest.assumptions``."""
    assumptions = [
        f"repository-type: {profile.repository_type}",
        f"primary-language: {profile.technology.primary_language}",
        f"build-system: {profile.build.build_system}",
        f"test-command: {profile.test.test_command}",
    ]
    if profile.technology.frameworks:
        assumptions.append(f"frameworks: {', '.join(profile.technology.frameworks)}")
    if profile.structure.source_dirs:
        assumptions.append(f"source-dirs: {', '.join(profile.structure.source_dirs)}")
    if profile.conventions.linters or profile.conventions.formatters:
        tools = ", ".join((*profile.conventions.linters, *profile.conventions.formatters))
        assumptions.append(f"conventions: {tools}")
    return tuple(assumptions)


# --------------------------------------------------------------------------- #
# small deterministic helpers
# --------------------------------------------------------------------------- #


def _dep_names(section: object) -> list[str]:
    return sorted(section.keys()) if isinstance(section, dict) else []


def _py_dependency_names(py: dict[str, object]) -> list[str]:
    project = py.get("project")
    deps = project.get("dependencies") if isinstance(project, dict) else None
    return _split_requirement_names(deps)


def _py_optional_names(py: dict[str, object]) -> list[str]:
    project = py.get("project")
    optional = project.get("optional-dependencies") if isinstance(project, dict) else None
    names: list[str] = []
    if isinstance(optional, dict):
        for group in optional.values():
            names.extend(_split_requirement_names(group))
    return names


def _split_requirement_names(deps: object) -> list[str]:
    if not isinstance(deps, list):
        return []
    names: list[str] = []
    for raw in deps:
        if not isinstance(raw, str):
            continue
        name = raw
        for sep in ("[", "==", ">=", "<=", "~=", ">", "<", "!=", ";", " "):
            name = name.split(sep)[0]
        name = name.strip().lower()
        if name:
            names.append(name)
    return names


def _pyproject_build_backend(py: dict[str, object]) -> str | None:
    system = py.get("build-system")
    if isinstance(system, dict):
        backend = system.get("build-backend")
        if isinstance(backend, str):
            return backend
    return None


def _pyproject_has_tool(py: dict[str, object], tool: str) -> bool:
    tools = py.get("tool")
    return isinstance(tools, dict) and tool in tools


def _has_pytest_config(py: dict[str, object]) -> bool:
    tools = py.get("tool")
    return isinstance(tools, dict) and "pytest" in tools


def _pyproject_line_length(py: dict[str, object]) -> int | None:
    tools = py.get("tool")
    if not isinstance(tools, dict):
        return None
    for tool in ("ruff", "black"):
        config = tools.get(tool)
        if isinstance(config, dict):
            length = config.get("line-length")
            if isinstance(length, int):
                return length
    return None


def _makefile_targets(root: str, top: set[str], evidence: list[str]) -> list[str]:
    name = "Makefile" if "Makefile" in top else "makefile"
    try:
        with open(os.path.join(root, name), encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    evidence.append(name)
    targets: list[str] = []
    for line in lines:
        if line and not line.startswith((" ", "\t", "#", ".")) and ":" in line:
            target = line.split(":", 1)[0].strip()
            if target and " " not in target and "=" not in target:
                targets.append(target)
    return sorted(set(targets))


def _read_codeowners(path: str) -> tuple[str, ...]:
    owners: set[str] = set()
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    owners.update(token for token in stripped.split()[1:] if token.startswith("@"))
    except OSError:
        return ()
    return tuple(sorted(owners))


def _empty_profile(root: str) -> RepositoryProfile:
    return RepositoryProfile(
        root=root,
        exists=False,
        repository_type="unknown",
        technology=TechnologyStack(None, (), (), ()),
        build=BuildProfile(None, (), ()),
        test=TestProfile((), (), None),
        documentation=DocumentationProfile(None, (), (), (), ()),
        structure=ProjectStructure((), (), ()),
        dependencies=DependencyProfile(None, (), ()),
        ci=CiProfile(None, ()),
        conventions=ConventionHints((), (), (), None, False, False),
        ownership=OwnershipHints(False, ()),
        file_count=0,
        evidence=(),
    )
