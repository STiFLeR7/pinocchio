"""Unit tests for nexus_runtime_adapters.selection — deterministic runtime selection (Milestone 5).

Selection depends only on required capabilities, declared capabilities, and policy — never on
heuristics or AI. It reuses the Runtime Manager's own match → health → policy → choose funnel,
so these tests assert determinism, capability filtering, policy allow/deny/prefer, and
fail-closed behaviour on an unsatisfiable requirement.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Reference
from nexus_runtime.validators import CapabilityMismatchError, NoEligibleRuntimeError
from nexus_runtime_adapters.catalog import build_default_adapter_registry
from nexus_runtime_adapters.selection import select_runtime


def _caps(*identifiers: str) -> tuple[Reference, ...]:
    return tuple(Reference(target_type="capability", identifier=i) for i in identifiers)


def test_selection_is_deterministic() -> None:
    registry = build_default_adapter_registry()
    a = select_runtime(registry, _caps("code_generation"), {})
    b = select_runtime(registry, _caps("code_generation"), {})
    assert a.chosen.identity == b.chosen.identity == "claude-code"  # lowest identity, no policy


def test_policy_prefers_a_runtime() -> None:
    registry = build_default_adapter_registry()
    chosen = select_runtime(
        registry, _caps("code_generation"), {"preferred_runtimes": ("gemini-cli",)}
    ).chosen
    assert chosen.identity == "gemini-cli"


def test_policy_allowlist_forces_a_runtime() -> None:
    registry = build_default_adapter_registry()
    chosen = select_runtime(
        registry, _caps("code_generation"), {"allowed_runtimes": ("shell",)}
    ).chosen
    assert chosen.identity == "shell"


def test_capability_filters_to_the_only_provider() -> None:
    registry = build_default_adapter_registry()
    # Only the shell advertises command_execution.
    chosen = select_runtime(registry, _caps("command_execution"), {}).chosen
    assert chosen.identity == "shell"


def test_unsatisfiable_capability_fails_closed() -> None:
    registry = build_default_adapter_registry()
    with pytest.raises(CapabilityMismatchError):
        select_runtime(registry, _caps("time_travel"), {})


def test_policy_denies_every_candidate_fails_closed() -> None:
    registry = build_default_adapter_registry()
    with pytest.raises(NoEligibleRuntimeError):
        select_runtime(
            registry,
            _caps("code_generation"),
            {"denied_runtimes": ("claude-code", "gemini-cli", "shell")},
        )


def test_candidate_ids_scopes_the_selection() -> None:
    registry = build_default_adapter_registry()
    chosen = select_runtime(
        registry, _caps("code_generation"), {}, candidate_ids=("gemini-cli", "shell")
    ).chosen
    assert chosen.identity == "gemini-cli"  # lowest among the scoped candidates


def test_selection_records_the_full_funnel() -> None:
    registry = build_default_adapter_registry()
    result = select_runtime(registry, _caps("code_generation"), {})
    assert set(result.eligible_ids) == {"claude-code", "gemini-cli", "shell"}
    assert result.required == ("code_generation",)
    assert result.chosen_match.eligible is True
