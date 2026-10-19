"""Capability Program 2 -- multi-agent runtime integration (cross-runtime validation).

Proves the Runtime abstraction is genuinely provider-independent: the same governed workflow
runs on Claude, Gemini, and Shell by **adapter substitution alone**, with identical governance
and only runtime-specific artifacts differing. Covers the adapter registry (Milestone 1),
cross-runtime compatibility (Milestone 4), deterministic selection (Milestone 5), and
cross-runtime governance equivalence + failure flow (Milestone 6).
"""

from __future__ import annotations

import pathlib

from nexus_core.contracts.base import Reference
from nexus_runtime_adapters import (
    CrossRuntimeRunner,
    build_default_adapter_registry,
    governance_signature,
)
from nexus_workflows import reference_request

_RUNTIMES = ("claude-code", "gemini-cli", "shell")


def _caps(*identifiers: str) -> tuple[Reference, ...]:
    return tuple(Reference(target_type="capability", identifier=i) for i in identifiers)


# --- Milestone 1: the adapter registry -------------------------------------- #


def test_default_registry_exposes_three_runtimes() -> None:
    registry = build_default_adapter_registry()
    assert registry.identities() == _RUNTIMES
    for identity in _RUNTIMES:
        assert "code_generation" in registry.capabilities(identity)


def test_runner_defaults_to_the_shipped_registry() -> None:
    # A runner with no explicit registry wires the default Claude/Gemini/Shell catalog.
    runner = CrossRuntimeRunner()
    assert runner.adapters.identities() == _RUNTIMES


# --- Milestone 4: cross-runtime compatibility ------------------------------- #


def test_same_work_packages_execute_on_every_runtime() -> None:
    runner = CrossRuntimeRunner()
    matrix = runner.run_matrix(reference_request(run="m4"))
    assert tuple(cr.runtime_identity for cr in matrix) == _RUNTIMES
    for cr in matrix:
        # The same two work packages ran and completed on every runtime.
        assert cr.run.work_package_ids == matrix[0].run.work_package_ids
        assert cr.run.execution_outcomes == ("completed", "completed")
        assert cr.run.succeeded


def test_only_adapter_selection_changes_runtime_artifacts() -> None:
    runner = CrossRuntimeRunner()
    claude = runner.run_on("claude-code", reference_request(run="art"))
    shell = runner.run_on("shell", reference_request(run="art"))
    claude_artifacts = sorted(r.identifier for r in claude.timeline.artifacts())
    shell_artifacts = sorted(r.identifier for r in shell.timeline.artifacts())
    # Runtime-specific artifacts differ (main.py vs output.txt) — the allowed difference.
    assert any("main.py" in a for a in claude_artifacts)
    assert any("output.txt" in a for a in shell_artifacts)
    assert claude_artifacts != shell_artifacts


# --- Milestone 5: deterministic runtime selection --------------------------- #


def test_selection_depends_only_on_capabilities_and_policy() -> None:
    runner = CrossRuntimeRunner()
    # No policy → lowest identity deterministically.
    assert runner.select(_caps("code_generation"), {}).chosen.identity == "claude-code"
    # Policy alone changes the choice — never a heuristic.
    assert (
        runner.select(_caps("code_generation"), {"preferred_runtimes": ("shell",)}).chosen.identity
        == "shell"
    )


# --- Milestone 6: cross-runtime governance equivalence ---------------------- #


def test_governance_is_identical_across_runtimes() -> None:
    runner = CrossRuntimeRunner()
    matrix = runner.run_matrix(reference_request(run="m6"))
    baseline = matrix[0].governance
    for cr in matrix:
        assert cr.governance == baseline, f"{cr.runtime_identity} diverged in governance"
    # The identical part includes the decisions and the runtime-independent event skeleton.
    assert baseline.validation_decisions == ("passed", "passed")
    assert baseline.recovery_decisions == ("complete", "complete")
    assert baseline.governance_event_types  # non-empty structural fingerprint


def test_failure_flow_is_identical_across_runtimes() -> None:
    runner = CrossRuntimeRunner()
    matrix = runner.run_matrix(reference_request(run="m6f", fail=True))
    baseline = matrix[0].governance
    for cr in matrix:
        assert cr.governance == baseline
        assert cr.run.execution_outcomes == ("failed", "failed")
        assert cr.run.validation_decisions == ("failed", "failed")
        assert cr.run.recovery_decisions == ("retry", "retry")


def test_each_runtime_is_byte_identical_across_repeat_runs() -> None:
    runner = CrossRuntimeRunner()
    for identity in _RUNTIMES:
        r1 = runner.run_on(identity, reference_request(run="det"))
        r2 = runner.run_on(identity, reference_request(run="det"))
        assert [(e.identifier, e.type, e.payload) for e in r1.events] == [
            (e.identifier, e.type, e.payload) for e in r2.events
        ]


def test_governance_signature_helper_matches_run() -> None:
    runner = CrossRuntimeRunner()
    run = runner.run_on("gemini-cli", reference_request(run="sig"))
    signature = governance_signature(run)
    assert signature.work_package_ids == run.work_package_ids
    assert signature.execution_outcomes == run.execution_outcomes
    assert signature.reflection_candidate_count == len(run.reflection_candidates)


# --- run_on wiring: explicit pipeline + shared knowledge -------------------- #


def test_run_on_carries_knowledge_across_runs() -> None:
    # Knowledge written on one runtime is served to a later run on a different runtime.
    from nexus_workflows import PipelineBuilder

    runner = CrossRuntimeRunner()
    first = PipelineBuilder().build()
    runner.run_on("claude-code", reference_request(run="feed1"), pipeline=first)
    shared = first.knowledge.repositories
    run2 = runner.run_on(
        "gemini-cli", reference_request(run="feed2"), knowledge_repositories=shared
    )
    assert run2.knowledge_consumed >= 1  # learning flowed across a runtime switch


# --- structural guardrail: registry/selection stay runtime-independent ------ #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _module_source(package: str, module: str) -> str:
    return (_REPO_ROOT / package / module).read_text(encoding="utf-8")


def test_registry_and_selection_name_no_concrete_provider() -> None:
    # The registry/selection core must not import a concrete adapter (doc 03 §3 litmus).
    for module in ("registry.py", "selection.py"):
        source = _module_source("nexus_runtime_adapters", module)
        assert "nexus_runtime_claude" not in source
        assert "nexus_runtime_gemini" not in source
        assert "nexus_runtime_shell" not in source
