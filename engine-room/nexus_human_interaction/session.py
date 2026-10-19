"""Interaction session reconstruction — rebuild the operator session from the ``interaction.*`` log.

The interaction session is a projection (INV-13/14): its state is a pure function of the durable
``interaction.*`` facts, so a reopened log reconstructs it exactly and a restart resumes it.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.domain.event import Event
from nexus_human_interaction import events as ievents
from nexus_human_interaction.model import InteractionSession


def reconstruct_interaction_session(
    events: tuple[Event, ...], session_id: str
) -> InteractionSession:
    """Rebuild one interaction session from the ``interaction.*`` stream (the log is truth)."""
    prefix = f"evt-{session_id}-"
    pipeline_ref = Reference(target_type="pipeline_session", identifier="")
    status = "pending"
    submitted = False
    responded = False
    knowledge_refs: tuple[Reference, ...] = ()
    stages: tuple[str, ...] = ()
    for event in events:
        if event.producer != ievents.INTERACTION_PRODUCER or not event.identifier.startswith(
            prefix
        ):
            continue
        if event.type == ievents.INTERACTION_SESSION_STARTED:
            pipeline_ref = Reference(
                target_type="pipeline_session",
                identifier=str(event.payload.get("pipeline_session", "")),
            )
            status = "running"
        elif event.type == ievents.INTERACTION_REQUEST_SUBMITTED:
            submitted = True
        elif event.type == ievents.INTERACTION_RESPONSE_RECORDED:
            responded = True
            status = str(event.payload.get("status", status))
            knowledge_refs = tuple(
                Reference(target_type="knowledge", identifier=str(identifier))
                for identifier in event.payload.get("knowledge_references", ())
            )
            stages = tuple(str(s) for s in event.payload.get("stages_completed", ()))
    return InteractionSession(
        identity=session_id,
        pipeline_session_ref=pipeline_ref,
        status=status,
        submitted=submitted,
        responded=responded,
        knowledge_references=knowledge_refs,
        stages_completed=stages,
    )
