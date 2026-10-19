"""Unit tests for the Skill domain model (contract: skill.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import SkillCategory
from nexus_core.domain.skill import Skill
from nexus_core.state.transitions import MACHINES


def _valid_skill() -> Skill:
    return Skill(
        identity="sk-1",
        name="Repository Analysis",
        version="1.0.0",
        purpose="Analyze a repository and report its structure.",
        inputs=({"role": "repository"},),
        outputs=({"role": "report"},),
        procedure={"phases": ["scan", "summarize"]},
    )


def test_construction() -> None:
    skill = _valid_skill()
    assert skill.identity == "sk-1"
    assert skill.purpose.startswith("Analyze")
    assert skill.status is None
    assert skill.constraints == ()
    assert skill.required_capabilities == ()


def test_construction_with_optionals() -> None:
    skill = Skill(
        identity="sk-2",
        name="Code Generation",
        version="2.0.0",
        purpose="Generate code from a spec.",
        inputs=({"role": "spec"},),
        outputs=({"role": "implementation"},),
        procedure={"phases": ["plan", "write"]},
        category=SkillCategory.DEVELOPMENT,
        required_capabilities=(Reference(target_type="capability", identifier="cap-1"),),
    )
    assert skill.category is SkillCategory.DEVELOPMENT
    assert skill.required_capabilities[0].identifier == "cap-1"


def test_immutable() -> None:
    skill = _valid_skill()
    with pytest.raises(ValidationError):
        skill.version = "9.9.9"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Skill(  # type: ignore[call-arg]
            identity="sk-1",
            name="Repository Analysis",
            version="1.0.0",
            purpose="Analyze a repository.",
            inputs=(),
            outputs=(),
            # procedure missing
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Skill(
            identity="sk-1",
            name="Repository Analysis",
            version="1.0.0",
            purpose="Analyze a repository.",
            inputs=(),
            outputs=(),
            procedure={},
            runtime="claude",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    skill = _valid_skill()
    assert Skill.model_validate(skill.model_dump()) == skill


def test_lifecycle_name() -> None:
    assert Skill.LIFECYCLE_NAME == "skill"
    assert Skill.LIFECYCLE_NAME in MACHINES
