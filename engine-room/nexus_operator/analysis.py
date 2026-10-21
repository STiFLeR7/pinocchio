"""Internal correlation helpers — project a workflow run's per-node governed outcomes.

For one run the execution / validation / recovery stages appear in **session order** (which is not
the declared work-item order), and ``validation_decisions`` / ``recovery_decisions`` are
index-aligned to that same order. So a correct per-work-package view keys on the *node*, not on the
work-package-id index. This module centralises that correlation for the explorer and dashboard;
it holds no engine logic, only projection of what Validation and Recovery already decided.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_workflows import WorkflowRun

_RAW_OUTPUT_MARKER = "captured-output"


@dataclass(frozen=True, slots=True)
class NodeOutcome:
    """The governed outcome for one node (one work package), correlated across stages."""

    node: str
    validation_decision: str
    recovery_decision: str
    deliverables: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def _node(label: str) -> str:
    return label.split(":", 1)[1] if ":" in label else label


def _at(decisions: tuple[str, ...], index: int) -> str:
    return decisions[index] if index < len(decisions) else "unknown"


def node_outcomes(run: WorkflowRun) -> tuple[NodeOutcome, ...]:
    """The per-node governed outcomes of ``run``, in the run's session order."""
    exec_by_node = {
        _node(stage.label): stage for stage in run.timeline.stages if stage.engine == "execution"
    }
    validation_stages = [s for s in run.timeline.stages if s.engine == "validation"]
    outcomes: list[NodeOutcome] = []
    for index, stage in enumerate(validation_stages):
        node = _node(stage.label)
        exec_stage = exec_by_node.get(node)
        deliverables = tuple(
            ref.identifier
            for ref in (exec_stage.artifact_refs if exec_stage is not None else ())
            if _RAW_OUTPUT_MARKER not in ref.identifier
        )
        outcomes.append(
            NodeOutcome(
                node=node,
                validation_decision=_at(run.validation_decisions, index),
                recovery_decision=_at(run.recovery_decisions, index),
                deliverables=deliverables,
                evidence_refs=tuple(ref.identifier for ref in stage.artifact_refs),
            )
        )
    return tuple(outcomes)


def work_package_for(node: str, work_package_ids: tuple[str, ...]) -> str:
    """The work-package id that corresponds to ``node`` (matched by shared step key)."""
    key = node.removeprefix("node-")
    return next((wp for wp in work_package_ids if wp.endswith(key)), node)
