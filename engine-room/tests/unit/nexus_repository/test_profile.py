"""Profile correctness — the RepositoryProfile is facts-only, complete, and deterministic."""

from __future__ import annotations

from nexus_repository import RepositoryProfile
from nexus_repository.engine import RepositoryIntelligence
from tests.unit.nexus_repository.fixtures import make_repo

_RI = RepositoryIntelligence(now=lambda: "t")


def _profile(root):
    return _RI.profile(root, persist=False)


def test_technology_and_type_are_facts(tmp_path) -> None:
    p = _profile(make_repo(tmp_path))
    assert p.technology.primary_language == "python"
    assert "FastAPI" in p.technology.frameworks and "Pydantic" in p.technology.frameworks
    assert "uv" in p.technology.package_managers
    assert p.repository_type.startswith("python")


def test_build_test_ci_conventions(tmp_path) -> None:
    p = _profile(make_repo(tmp_path))
    assert p.build.build_system == "hatchling.build"
    assert p.test.frameworks == ("pytest",) and p.test.test_command == "pytest"
    assert "tests" in p.test.test_dirs
    assert p.ci.system == "github-actions" and p.ci.workflows == ("ci.yml",)
    assert "ruff" in p.conventions.linters and p.conventions.line_length == 100


def test_constitutional_artifacts_discovered(tmp_path) -> None:
    p = _profile(make_repo(tmp_path))
    assert any(f.endswith("ADR-001.md") for f in p.constitutional.adr_files)
    assert any(f.endswith("thing.md") for f in p.constitutional.contract_files)
    assert any("INVARIANT" in f.upper() for f in p.constitutional.invariant_files)


def test_health_signals_are_presence_facts(tmp_path) -> None:
    p = _profile(make_repo(tmp_path))
    assert p.health.has_readme and p.health.has_tests and p.health.has_ci
    assert p.health.has_lockfile and p.health.has_license
    assert p.health.file_count == p.file_count > 0


def test_profile_is_deterministic_across_repeated_scans(tmp_path) -> None:
    root = make_repo(tmp_path)
    a = _profile(root)
    b = _profile(root)
    assert a == b
    assert a.identity == b.identity


def test_profile_reconstructs_from_serialized_form(tmp_path) -> None:
    p = _profile(make_repo(tmp_path))
    assert RepositoryProfile.model_validate(p.model_dump(mode="json")) == p


def test_missing_repository_yields_empty_deterministic_profile() -> None:
    a = _profile("/nonexistent/path/xyz")
    b = _profile("/nonexistent/path/xyz")
    assert a.exists is False and a.repository_type == "unknown"
    assert a.identity == b.identity


def test_as_facts_contains_only_facts(tmp_path) -> None:
    facts = _profile(make_repo(tmp_path)).as_facts()
    assert facts["primary_language"] == "python"
    assert facts["has_tests"] is True
    # no opinion/recommendation/strategy keys
    for banned in ("recommendation", "strategy", "approach", "should", "estimate"):
        assert not any(banned in k for k in facts)
