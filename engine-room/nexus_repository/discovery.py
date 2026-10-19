"""Evidence discovery — deterministic fact extractors over the snapshot + manifests.

Promoted from the A2 ``repo_profile`` prototype (logic unchanged): technology/framework detection,
dependency discovery, build-system detection, test-framework detection, documentation + ADR
discovery, workspace structure, CI discovery, coding-convention extraction, and ownership — all
**facts on disk** (manifests, config, CI dirs, doc locations). No embeddings, no semantic search, no
opinions. Same evidence in → same facts out.
"""

from __future__ import annotations

import json
import os
import tomllib

from nexus_repository.profile import (
    BuildProfile,
    CiProfile,
    ConventionHints,
    DependencyProfile,
    DocumentationProfile,
    OwnershipHints,
    ProjectStructure,
    TechnologyStack,
    TestProfile,
)
from nexus_repository.scanner import RepositorySnapshot

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


def read_pyproject(root: str, top: set[str], evidence: list[str]) -> dict[str, object]:
    if "pyproject.toml" not in top:
        return {}
    try:
        with open(os.path.join(root, "pyproject.toml"), "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    evidence.append("pyproject.toml")
    return data


def read_package_json(root: str, top: set[str], evidence: list[str]) -> dict[str, object]:
    if "package.json" not in top:
        return {}
    try:
        with open(os.path.join(root, "package.json"), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    evidence.append("package.json")
    return data if isinstance(data, dict) else {}


def technology(
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
    for name in py_dependency_names(py):
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


def dependencies(py: dict[str, object], pkg: dict[str, object]) -> DependencyProfile:
    if pkg:
        return DependencyProfile(
            manifest="package.json",
            direct=tuple(sorted(_dep_names(pkg.get("dependencies")))),
            dev=tuple(sorted(_dep_names(pkg.get("devDependencies")))),
        )
    if py:
        return DependencyProfile(
            manifest="pyproject.toml",
            direct=tuple(sorted(py_dependency_names(py))),
            dev=tuple(sorted(_py_optional_names(py))),
        )
    return DependencyProfile(manifest=None, direct=(), dev=())


def build(
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


def test(
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
    py_names = set(py_dependency_names(py)) | set(_py_optional_names(py))
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


def documentation(
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


def structure(root: str, snapshot: RepositorySnapshot, top: set[str]) -> ProjectStructure:
    dirs = tuple(sorted(d for d in snapshot.entries if os.path.isdir(os.path.join(root, d))))
    source_dirs = tuple(
        d for d in ("src", "app", "lib", "pkg", "internal", "components") if d in top
    )
    entry_points = tuple(
        sorted(e for e in _ENTRY_CANDIDATES if os.path.exists(os.path.join(root, e)))
    )
    return ProjectStructure(top_level_dirs=dirs, source_dirs=source_dirs, entry_points=entry_points)


def ci(root: str, top: set[str], evidence: list[str]) -> CiProfile:
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


def conventions(
    root: str, top: set[str], py: dict[str, object], pkg: dict[str, object], evidence: list[str]
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
    pre_commit = ".pre-commit-config.yaml" in top
    if pre_commit:
        evidence.append(".pre-commit-config.yaml")
    return ConventionHints(
        formatters=tuple(dict.fromkeys(formatters)),
        linters=tuple(dict.fromkeys(linters)),
        type_checkers=tuple(dict.fromkeys(type_checkers)),
        line_length=_pyproject_line_length(py),
        editorconfig=".editorconfig" in top,
        pre_commit=pre_commit,
    )


def ownership(root: str, top: set[str], evidence: list[str]) -> OwnershipHints:
    for loc in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
        path = os.path.join(root, *loc.split("/"))
        if os.path.isfile(path):
            evidence.append(loc)
            return OwnershipHints(codeowners=True, owners=_read_codeowners(path))
    return OwnershipHints(codeowners=False, owners=())


def repository_type(
    technology: TechnologyStack, structure: ProjectStructure, test: TestProfile
) -> str:
    """Project classification — a *fact* about the project kind (never engineering-work classification)."""
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


# -- helpers (unchanged from the A2 prototype) ------------------------------- #


def _dep_names(section: object) -> list[str]:
    return sorted(section.keys()) if isinstance(section, dict) else []


def py_dependency_names(py: dict[str, object]) -> list[str]:
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
        length = config.get("line-length") if isinstance(config, dict) else None
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
