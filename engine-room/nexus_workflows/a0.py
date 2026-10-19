"""A0 -- the real end-to-end engineering vertical (architecture validation).

This module is the *thin bridge* the Architecture Freeze Review called for: it drives the ten
already-built engines (via :class:`~nexus_workflows.coordinator.WorkflowCoordinator`) against a
**real** Claude Code session over a **real** working directory, adds the two capabilities the
coordinator's deterministic reference path stubs -- real repository grounding
(:mod:`nexus_workflows.repo_intelligence`) and an independent, on-disk validation of the actual
filesystem effect -- and gates the one dangerous operation (commit/push) **fail-closed** (INV-30).

It introduces no new pipeline stage and no new domain concept. The only provider-specific choice is
the injected ``adapter_factory`` (the coordinator's sanctioned seam); everything else is the
existing pipeline. Nothing upstream imports this module.

Design boundaries honored:
* the real repo path reaches Claude only through the runtime adapter's ``working_dir`` -- the
  Execution Engine performs; it does not re-configure (doc: engine drives ``adapter.execute``);
* the file effect is judged by reading the disk, never by Claude's self-report (INV-20);
* no answer / no authorization for a governed action is never an implicit grant (INV-30).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field

from nexus_context import RawContextFragment
from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import (
    CapabilityCategory,
    Domain,
    InterpretationConfidence,
    KnowledgeType,
    Priority,
    SkillCategory,
)
from nexus_core.domain import Capability, Goal, Scope
from nexus_core.domain.skill import Skill
from nexus_planning import WorkItemSpec
from nexus_runtime_claude import ClaudeRuntimeAdapter
from nexus_runtime_claude.invoker import ClaudeCliInvoker
from nexus_workflows.coordinator import AdapterFactory, WorkflowCoordinator, WorkflowRun
from nexus_workflows.pipeline import Pipeline, PipelineBuilder
from nexus_workflows.repo_intelligence import (
    RepositorySnapshot,
    read_repository,
    to_context_fragments,
)
from nexus_workflows.request import WorkflowRequest

_A0_CAPABILITY = "code_generation"
_A0_SKILL = "skill-a0"


# --------------------------------------------------------------------------- #
# Task + authorization + result value objects
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class A0TaskSpec:
    """One engineering task, plus the independent check that decides if it truly happened."""

    objective: str
    knowledge_subject: str
    verify_relpath: str
    verify_expected: str
    identity: str = "a0"


@dataclass(frozen=True, slots=True)
class Authorization:
    """A recorded human authorization for governed operations (INV-17: input captured as data)."""

    approver: str
    reason: str
    granted_operations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """The settled outcome of one approval gate (carries no policy; it records a human answer)."""

    operation: str
    granted: bool
    approver: str
    reason: str


class ApprovalGate:
    """Fail-closed approval gate for dangerous operations (INV-30).

    HI/Governance would normally *reach* the human and *evaluate* the policy; here the gate is the
    minimal, reusable enforcement point: absent an explicit recorded authorization for the exact
    operation, it **denies**. Silence is never consent.
    """

    def evaluate(self, *, operation: str, authorization: Authorization | None) -> ApprovalDecision:
        if authorization is not None and operation in authorization.granted_operations:
            return ApprovalDecision(
                operation=operation,
                granted=True,
                approver=authorization.approver,
                reason=authorization.reason,
            )
        return ApprovalDecision(
            operation=operation,
            granted=False,
            approver="none",
            reason="fail-closed: no human authorization recorded for this operation (INV-30)",
        )


@dataclass(frozen=True, slots=True)
class A0Result:
    """The full evidence of one A0 vertical run."""

    task: A0TaskSpec
    working_dir: str
    snapshot: RepositorySnapshot
    run: WorkflowRun
    independent_validation_ok: bool
    independent_validation_detail: str
    commit_decision: ApprovalDecision
    committed: bool
    knowledge_item_ids: tuple[str, ...]
    remaining_stubs: tuple[str, ...]
    briefing: str = field(default="")


# --------------------------------------------------------------------------- #
# Real Claude actuation seam
# --------------------------------------------------------------------------- #


def real_claude_adapter_factory(
    working_dir: str, *, permission_mode: str = "acceptEdits"
) -> AdapterFactory:
    """Build the coordinator's adapter factory that drives the **real** ``claude`` CLI at ``working_dir``.

    ``ClaudeCliInvoker`` already adds ``--output-format stream-json --verbose``; we add only the
    permission mode so the headless session may apply edits without an interactive prompt (safe
    because A0 runs in an isolated, throwaway workspace).
    """

    def factory(_request: WorkflowRequest) -> ClaudeRuntimeAdapter:
        invoker = ClaudeCliInvoker(extra_args=("--permission-mode", permission_mode))
        return ClaudeRuntimeAdapter(invoker=invoker, working_dir=working_dir)

    return factory


# --------------------------------------------------------------------------- #
# Request construction (reuses existing value objects; no new concept)
# --------------------------------------------------------------------------- #


def build_a0_request(
    task: A0TaskSpec, context_fragments: Sequence[RawContextFragment]
) -> WorkflowRequest:
    """Assemble a single-work-item :class:`WorkflowRequest` from a task + real repo context."""
    goal = Goal(
        identity=f"goal-{task.identity}",
        outcome=task.objective,
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(),
        scope=Scope(included=("repository",), excluded=()),
    )
    capability = Capability(
        identifier=_A0_CAPABILITY,
        name="Code Generation",
        version="1",
        category=CapabilityCategory.DEVELOPMENT,
        description="modify repository files to satisfy an engineering objective",
        inputs=(),
        outputs=(),
    )
    skill = Skill(
        identity=_A0_SKILL,
        name="A0 Engineering Skill",
        version="1",
        purpose="perform the engineering task in the working directory",
        inputs=(),
        outputs=(),
        procedure={},
        category=SkillCategory.DEVELOPMENT,
        required_capabilities=(Reference(target_type="capability", identifier=_A0_CAPABILITY),),
    )
    work_item = WorkItemSpec(
        key="a0",
        objective=task.objective,
        capability_requirements=(_A0_CAPABILITY,),
        skill_refs=(Reference(target_type="skill", identifier=_A0_SKILL),),
    )
    return WorkflowRequest(
        goal=goal,
        work_items=(work_item,),
        knowledge_subject=task.knowledge_subject,
        scope=f"wf-{task.identity}",
        context_fragments=tuple(context_fragments),
        capabilities=(capability,),
        skills=(skill,),
        knowledge_kind=KnowledgeType.LESSON,
        correlation_identifier=f"cor-{task.identity}",
    )


# --------------------------------------------------------------------------- #
# The vertical
# --------------------------------------------------------------------------- #


def run_a0_vertical(
    task: A0TaskSpec,
    *,
    working_dir: str,
    pipeline: Pipeline | None = None,
    adapter_factory: AdapterFactory | None = None,
    commit_authorization: Authorization | None = None,
) -> A0Result:
    """Run the full Goal->Knowledge pipeline against ``working_dir`` and validate the real effect.

    ``adapter_factory`` defaults to the **real** Claude CLI at ``working_dir``. Pass a stub factory
    for deterministic tests. The commit/push step is always gated (fail-closed by default).
    """
    snapshot = read_repository(working_dir)
    fragments = to_context_fragments(snapshot)
    request = build_a0_request(task, fragments)

    pipeline = pipeline or PipelineBuilder().build()
    factory = adapter_factory or real_claude_adapter_factory(working_dir)
    coordinator = WorkflowCoordinator(pipeline, adapter_factory=factory)
    run = coordinator.run(request)

    ok, detail = _independent_validate(working_dir, task)

    # The one dangerous operation in the reference workflow: persisting work (commit/push). It is
    # gated fail-closed. Even when authorized, A0 deliberately does not write back to the real
    # repository (the run operates on an isolated copy) -- the grant is recorded, the act deferred.
    decision = ApprovalGate().evaluate(operation="git_commit", authorization=commit_authorization)
    committed = False

    result = A0Result(
        task=task,
        working_dir=working_dir,
        snapshot=snapshot,
        run=run,
        independent_validation_ok=ok,
        independent_validation_detail=detail,
        commit_decision=decision,
        committed=committed,
        knowledge_item_ids=run.knowledge_item_ids,
        remaining_stubs=_remaining_stubs(),
    )
    return _with_briefing(result)


def _independent_validate(working_dir: str, task: A0TaskSpec) -> tuple[bool, str]:
    """Judge the real filesystem effect independently of Claude's self-report (INV-20)."""
    target = os.path.join(working_dir, task.verify_relpath)
    if not os.path.isfile(target):
        return False, f"expected artifact '{task.verify_relpath}' was not created on disk"
    try:
        with open(target, encoding="utf-8") as handle:
            content = handle.read()
    except OSError as exc:
        return False, f"could not read '{task.verify_relpath}': {exc}"
    if task.verify_expected in content:
        return True, (
            f"verified on disk: '{task.verify_relpath}' contains expected marker "
            f"'{task.verify_expected}'"
        )
    return False, (
        f"'{task.verify_relpath}' exists but does not contain expected marker "
        f"'{task.verify_expected}'"
    )


def _remaining_stubs() -> tuple[str, ...]:
    """The honest, explicit list of what A0 does NOT yet realize (for the report)."""
    return (
        "commit/push to the real repository (gated fail-closed; A0 runs on an isolated copy)",
        "human approval via a real channel (Human Interaction) -- gate is code-local, not routed",
        "governed Actuation session (reattach/permission-envelope) -- uses a one-shot CLI invoker",
        "Engineering Intelligence approach/methodology selection -- objective is passed through",
        "Intent Resolution / clarification loop -- the Goal is constructed directly",
    )


def _with_briefing(result: A0Result) -> A0Result:
    """Attach a short human-readable briefing (the reference 'report back' step)."""
    run = result.run
    verdict = "SUCCEEDED" if result.independent_validation_ok else "DID NOT VALIDATE"
    lines = [
        f"# A0 Vertical Briefing -- {verdict}",
        f"objective       : {result.task.objective}",
        f"working_dir     : {result.working_dir}",
        f"repo grounded   : {result.snapshot.file_count} files, "
        f"langs={list(result.snapshot.languages)}, key_docs={list(result.snapshot.key_documents)}",
        f"execution       : {list(run.execution_outcomes)}",
        f"validation      : {list(run.validation_decisions)}",
        f"recovery        : {list(run.recovery_decisions)}",
        f"independent chk : {result.independent_validation_detail}",
        f"commit gate     : {'GRANTED' if result.commit_decision.granted else 'DENIED'} "
        f"({result.commit_decision.reason})",
        f"committed       : {result.committed}",
        f"knowledge       : {list(result.knowledge_item_ids)}",
        f"events recorded : {len(run.events)}",
    ]
    briefing = "\n".join(lines)
    return A0Result(
        task=result.task,
        working_dir=result.working_dir,
        snapshot=result.snapshot,
        run=result.run,
        independent_validation_ok=result.independent_validation_ok,
        independent_validation_detail=result.independent_validation_detail,
        commit_decision=result.commit_decision,
        committed=result.committed,
        knowledge_item_ids=result.knowledge_item_ids,
        remaining_stubs=result.remaining_stubs,
        briefing=briefing,
    )
