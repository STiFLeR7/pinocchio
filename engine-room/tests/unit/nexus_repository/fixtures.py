"""Shared fixtures for the Repository Intelligence (P7) suite — a controlled, deterministic repo."""

from __future__ import annotations

from pathlib import Path

from nexus_infra import build_infrastructure
from nexus_repository import build_repository

_NOW = "2026-01-01T00:00:00Z"

_PYPROJECT = """\
[project]
name = "sample"
dependencies = ["fastapi>=0.1", "pydantic"]

[project.optional-dependencies]
dev = ["pytest"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
"""


def make_repo(tmp_path: Path) -> str:
    """Create a small, fully-deterministic Python repository on disk and return its root."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Sample\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")

    pkg_a = tmp_path / "pkg_a"
    pkg_a.mkdir()
    (pkg_a / "__init__.py").write_text("from pkg_b import thing\n", encoding="utf-8")
    (pkg_a / "core.py").write_text("import pkg_b\nimport os\n", encoding="utf-8")

    pkg_b = tmp_path / "pkg_b"
    pkg_b.mkdir()
    (pkg_b / "__init__.py").write_text("thing = 1\n", encoding="utf-8")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")

    adr = tmp_path / "adr"
    adr.mkdir()
    (adr / "ADR-001.md").write_text("# ADR-001\n", encoding="utf-8")

    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "thing.md").write_text("# contract\n", encoding="utf-8")

    (tmp_path / "99_INVARIANTS.md").write_text("# invariants\n", encoding="utf-8")

    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    return str(tmp_path)


def wired(now=lambda: _NOW):
    infra = build_infrastructure()
    return infra, build_repository(infra, now=now)
