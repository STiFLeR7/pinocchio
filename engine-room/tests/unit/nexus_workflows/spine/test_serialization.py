"""P16 support — SpineRequest (de)serialization round-trips exactly (durable schedules depend on it)."""

from __future__ import annotations

from nexus_workflows.spine import dump_spine_request, load_spine_request, spine_reference_request


def test_spine_request_round_trips_through_a_json_payload() -> None:
    request = spine_reference_request(run="r1", gated=("review",))
    payload = dump_spine_request(request)
    assert isinstance(payload, dict) and payload["identity"] == request.identity
    assert load_spine_request(payload) == request  # exact round-trip


def test_serialized_payload_is_json_native() -> None:
    import json

    request = spine_reference_request(run="r1")
    json.dumps(dump_spine_request(request))  # no non-serializable value survives the dump
