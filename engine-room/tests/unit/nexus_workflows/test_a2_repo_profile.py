"""A2 Repository Intelligence -- deterministic profile tests on synthetic + real repos.

Covers: language/framework/build/test/CI/convention detection from evidence, determinism (same repo
in -> same profile out), the four benchmark queries, and real Planning consumption of the profile.
No embeddings, no network, no memory.
"""

from __future__ import annotations

import json
import pathlib

from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.domain import Goal, Scope
from nexus_planning import PlanningRequest, WorkItemSpec
from nexus_workflows.pipeline import PipelineBuilder
from nexus_workflows.repo_profile import (
    docs_to_consult,
    how_is_it_built,
    profile_repository,
    profile_to_assumptions,
    profile_to_context_fragments,
    relevant_tests,
    where_to_fix,
)


def _python_repo(root: pathlib.Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["fastapi>=0.1", "pydantic~=2.0"]\n'
        '[project.optional-dependencies]\ndev = ["pytest>=8"]\n'
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        "[tool.ruff]\nline-length = 99\n[tool.mypy]\nstrict = true\n[tool.pytest.ini_options]\n",
        encoding="utf-8",
    )
    (root / "Makefile").write_text("build:\n\techo build\ntest:\n\tpytest\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "src").mkdir()
    (root / ".pre-commit-config.yaml").write_text("repos: []", encoding="utf-8")
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("on: push", encoding="utf-8")


def _node_repo(root: pathlib.Path) -> None:
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "web",
                "dependencies": {"next": "14", "react": "18"},
                "devDependencies": {"eslint": "9", "vitest": "1"},
                "scripts": {"build": "next build", "test": "vitest"},
            }
        ),
        encoding="utf-8",
    )
    (root / "package-lock.json").write_text("{}", encoding="utf-8")
    (root / "tsconfig.json").write_text("{}", encoding="utf-8")
    (root / "app").mkdir()
    (root / "CLAUDE.md").write_text("# conventions", encoding="utf-8")


# --- detection from evidence ------------------------------------------------ #


def test_python_repo_profile(tmp_path: pathlib.Path) -> None:
    _python_repo(tmp_path)
    p = profile_repository(str(tmp_path))
    assert p.repository_type.startswith("python")
    assert p.technology.primary_language == "python"
    assert "FastAPI" in p.technology.frameworks and "Pydantic" in p.technology.frameworks
    assert p.build.build_system == "make"
    assert p.test.frameworks == ("pytest",) and p.test.test_command == "pytest"
    assert p.ci.system == "github-actions"
    assert "ruff" in p.conventions.linters and "mypy" in p.conventions.type_checkers
    assert p.conventions.line_length == 99
    assert p.conventions.pre_commit is True
    assert "fastapi" in p.dependencies.direct and "pytest" in p.dependencies.dev


def test_node_repo_profile(tmp_path: pathlib.Path) -> None:
    _node_repo(tmp_path)
    p = profile_repository(str(tmp_path))
    assert p.repository_type == "nextjs-web-app"
    assert "Next.js" in p.technology.frameworks and "React" in p.technology.frameworks
    assert p.technology.package_managers == ("npm",)
    assert "npm run build" in p.build.build_commands
    assert "vitest" in p.test.frameworks
    assert "eslint" in p.conventions.linters and "typescript" in p.conventions.type_checkers
    assert "app" in p.structure.source_dirs
    assert "CLAUDE.md" in p.documentation.agent_docs


def test_missing_repo_is_honest() -> None:
    p = profile_repository(r"D:\definitely-not-here-a2")
    assert p.exists is False and p.repository_type == "unknown"


# --- determinism ------------------------------------------------------------ #


def test_profile_is_deterministic(tmp_path: pathlib.Path) -> None:
    _python_repo(tmp_path)
    assert profile_repository(str(tmp_path)) == profile_repository(str(tmp_path))


# --- benchmark queries ------------------------------------------------------ #


def test_queries_are_evidence_backed(tmp_path: pathlib.Path) -> None:
    _python_repo(tmp_path)
    (tmp_path / "src" / "payment.py").write_text("# pay", encoding="utf-8")
    p = profile_repository(str(tmp_path))
    assert "make" in how_is_it_built(p).answer
    assert "pytest" in relevant_tests(p).answer
    assert docs_to_consult(p).evidence  # ordered doc sources
    fix = where_to_fix(p, "payment bug")
    assert any("payment" in e for e in fix.evidence)  # located by evidence, not inference


# --- integration: Planning consumes the profile (no engine change) ---------- #


def test_planning_consumes_profile_assumptions(tmp_path: pathlib.Path) -> None:
    _node_repo(tmp_path)
    p = profile_repository(str(tmp_path))
    assumptions = profile_to_assumptions(p)
    assert assumptions

    pipeline = PipelineBuilder().build()
    goal = Goal(
        identity="g",
        outcome="fix bug",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(),
        scope=Scope(included=("app",), excluded=()),
    )
    result = pipeline.planning.service.plan(
        goal,
        PlanningRequest(
            work_items=(WorkItemSpec(key="f", objective="fix"),), assumptions=assumptions
        ),
    )
    # The profile's grounding is carried, unchanged, into the built Plan.
    assert tuple(result.plan.assumptions) == assumptions
    assert any("nextjs" in a for a in result.plan.assumptions)


def test_context_fragments_carry_profile(tmp_path: pathlib.Path) -> None:
    _node_repo(tmp_path)
    fragments = profile_to_context_fragments(profile_repository(str(tmp_path)))
    keys = {f.key for f in fragments}
    assert keys == {"repository_profile", "repository_conventions"}
    profile_fragment = next(f for f in fragments if f.key == "repository_profile")
    assert profile_fragment.payload["repository_type"] == "nextjs-web-app"
