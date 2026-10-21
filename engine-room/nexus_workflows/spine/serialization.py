"""SpineRequest (de)serialization — a durable, replayable form of the pipeline's text-first input.

The spine owns :class:`SpineRequest` and its serialization (it already owns the nested value types). A
consumer that must persist *what to run* later — e.g. the P16 Scheduler storing a Goal to dispatch on a
schedule — dumps the request to a JSON-safe :class:`Struct` and reloads it, without importing any engine.
Round-trip is exact: the reloaded request is equal to the original.
"""

from __future__ import annotations

from nexus_context import RawContextFragment
from nexus_core.contracts.base import Struct
from nexus_core.contracts.enums import KnowledgeType
from nexus_core.domain import Capability
from nexus_planning import WorkItemSpec
from nexus_workflows.spine.model import SpineRequest


def dump_spine_request(request: SpineRequest) -> Struct:
    """Serialize a :class:`SpineRequest` to a JSON-safe payload (all nested values are ValueObjects)."""
    return {
        "identity": request.identity,
        "request_text": request.request_text,
        "work_items": [item.model_dump(mode="json") for item in request.work_items],
        "knowledge_subject": request.knowledge_subject,
        "scope": request.scope,
        "knowledge_kind": request.knowledge_kind.value,
        "context_fragments": [
            fragment.model_dump(mode="json") for fragment in request.context_fragments
        ],
        "capabilities": [capability.model_dump(mode="json") for capability in request.capabilities],
        "fail": request.fail,
        "correlation_identifier": request.correlation_identifier,
    }


def load_spine_request(payload: Struct) -> SpineRequest:
    """Reconstruct a :class:`SpineRequest` from a payload produced by :func:`dump_spine_request`."""
    return SpineRequest(
        identity=str(payload["identity"]),
        request_text=str(payload["request_text"]),
        work_items=tuple(
            WorkItemSpec.model_validate(item) for item in payload.get("work_items", ())
        ),
        knowledge_subject=str(payload["knowledge_subject"]),
        scope=str(payload["scope"]),
        knowledge_kind=KnowledgeType(payload["knowledge_kind"]),
        context_fragments=tuple(
            RawContextFragment.model_validate(fragment)
            for fragment in payload.get("context_fragments", ())
        ),
        capabilities=tuple(
            Capability.model_validate(capability) for capability in payload.get("capabilities", ())
        ),
        fail=bool(payload.get("fail", False)),
        correlation_identifier=str(payload.get("correlation_identifier", "")),
    )
