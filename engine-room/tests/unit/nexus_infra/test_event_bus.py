"""Unit tests for the in-process event bus (AP-201).

Covers subscribe/publish delivery, predicate filtering, unsubscribe semantics,
failure isolation with dead-lettering, and observability instrumentation.
"""

from __future__ import annotations

from nexus_core.domain.event import Event
from nexus_infra import (
    DeadLetter,
    InfraEventType,
    InMemoryObservability,
    InProcessEventBus,
    accept_all,
    by_correlation,
    by_type,
)
from tests.unit.nexus_infra.factories import make_event


class RecordingHandler:
    """An ``EventHandler`` that appends every delivered event to a list."""

    def __init__(self) -> None:
        self.received: list[Event] = []

    def handle(self, event: Event) -> None:
        self.received.append(event)


class FailingHandler:
    """An ``EventHandler`` whose :meth:`handle` always raises."""

    def __init__(self, message: str = "boom") -> None:
        self.message = message

    def handle(self, event: Event) -> None:
        raise RuntimeError(self.message)


# -- subscribe + publish ----------------------------------------------------- #


def test_subscribe_then_publish_delivers_to_handler() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    event = make_event()

    bus.subscribe(handler)
    bus.publish(event)

    assert handler.received == [event]


def test_publish_with_no_subscribers_is_a_noop() -> None:
    bus = InProcessEventBus()

    bus.publish(make_event())  # must not raise

    assert bus.subscription_count == 0


def test_multiple_handlers_all_receive_in_subscription_order() -> None:
    bus = InProcessEventBus()
    order: list[str] = []

    class Ordered:
        def __init__(self, label: str) -> None:
            self.label = label

        def handle(self, event: Event) -> None:
            order.append(self.label)

    first, second, third = Ordered("first"), Ordered("second"), Ordered("third")
    bus.subscribe(first)
    bus.subscribe(second)
    bus.subscribe(third)

    bus.publish(make_event())

    assert order == ["first", "second", "third"]


def test_same_handler_receives_every_published_event() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    bus.subscribe(handler)

    first = make_event(identifier="evt-1")
    second = make_event(identifier="evt-2")
    bus.publish(first)
    bus.publish(second)

    assert handler.received == [first, second]


# -- filtering --------------------------------------------------------------- #


def test_by_type_only_receives_matching_events() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    bus.subscribe(handler, by_type("a.b"))

    matching = make_event(identifier="m", type="a.b")
    other = make_event(identifier="o", type="x.y")
    bus.publish(matching)
    bus.publish(other)

    assert handler.received == [matching]


def test_by_type_accepts_any_of_several_types() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    bus.subscribe(handler, by_type("a.b", "c.d"))

    a = make_event(identifier="a", type="a.b")
    c = make_event(identifier="c", type="c.d")
    e = make_event(identifier="e", type="e.f")
    for event in (a, c, e):
        bus.publish(event)

    assert handler.received == [a, c]


def test_by_correlation_filters_by_stream() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    bus.subscribe(handler, by_correlation("cor-x"))

    in_stream = make_event(identifier="in", correlation_identifier="cor-x")
    out_stream = make_event(identifier="out", correlation_identifier="cor-y")
    bus.publish(in_stream)
    bus.publish(out_stream)

    assert handler.received == [in_stream]


def test_accept_all_is_the_default_and_receives_everything() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    bus.subscribe(handler)  # default predicate is accept_all

    events = [
        make_event(identifier="1", type="a.b"),
        make_event(identifier="2", type="c.d", correlation_identifier="cor-z"),
    ]
    for event in events:
        bus.publish(event)

    assert handler.received == events


def test_accept_all_passed_explicitly_receives_everything() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    bus.subscribe(handler, accept_all)

    event = make_event(type="anything.at.all")
    bus.publish(event)

    assert handler.received == [event]


def test_filters_are_independent_per_subscription() -> None:
    bus = InProcessEventBus()
    typed = RecordingHandler()
    catch_all = RecordingHandler()
    bus.subscribe(typed, by_type("a.b"))
    bus.subscribe(catch_all)

    matching = make_event(identifier="m", type="a.b")
    other = make_event(identifier="o", type="x.y")
    bus.publish(matching)
    bus.publish(other)

    assert typed.received == [matching]
    assert catch_all.received == [matching, other]


# -- unsubscribe / subscription_count ---------------------------------------- #


def test_unsubscribe_stops_further_delivery() -> None:
    bus = InProcessEventBus()
    handler = RecordingHandler()
    bus.subscribe(handler)

    bus.publish(make_event(identifier="before"))
    bus.unsubscribe(handler)
    bus.publish(make_event(identifier="after"))

    assert [e.identifier for e in handler.received] == ["before"]


def test_unsubscribe_unknown_handler_is_a_noop() -> None:
    bus = InProcessEventBus()
    subscribed = RecordingHandler()
    stranger = RecordingHandler()
    bus.subscribe(subscribed)

    bus.unsubscribe(stranger)  # must not raise

    assert bus.subscription_count == 1
    event = make_event()
    bus.publish(event)
    assert subscribed.received == [event]


def test_subscription_count_reflects_subscribe_and_unsubscribe() -> None:
    bus = InProcessEventBus()
    assert bus.subscription_count == 0

    first = RecordingHandler()
    second = RecordingHandler()
    bus.subscribe(first)
    assert bus.subscription_count == 1
    bus.subscribe(second)
    assert bus.subscription_count == 2

    bus.unsubscribe(first)
    assert bus.subscription_count == 1
    bus.unsubscribe(second)
    assert bus.subscription_count == 0


# -- dead-letter / failure isolation ----------------------------------------- #


def test_failing_handler_does_not_propagate() -> None:
    bus = InProcessEventBus()
    bus.subscribe(FailingHandler())

    bus.publish(make_event())  # must not raise


def test_failure_is_isolated_so_later_handler_still_receives() -> None:
    bus = InProcessEventBus()
    healthy = RecordingHandler()
    bus.subscribe(FailingHandler())
    bus.subscribe(healthy)  # subscribed AFTER the failing one

    event = make_event()
    bus.publish(event)

    assert healthy.received == [event]


def test_dead_letter_records_event_handler_and_error() -> None:
    bus = InProcessEventBus()
    bus.subscribe(FailingHandler("kaboom"))

    event = make_event()
    bus.publish(event)

    assert len(bus.dead_letters) == 1
    dead = bus.dead_letters[0]
    assert isinstance(dead, DeadLetter)
    assert dead.event is event
    assert dead.handler == "FailingHandler"
    assert dead.error  # non-empty
    assert "kaboom" in dead.error


def test_clear_dead_letters_empties_the_record() -> None:
    bus = InProcessEventBus()
    bus.subscribe(FailingHandler())
    bus.publish(make_event())
    assert len(bus.dead_letters) == 1

    bus.clear_dead_letters()

    assert bus.dead_letters == ()


def test_each_failing_delivery_produces_its_own_dead_letter() -> None:
    bus = InProcessEventBus()
    bus.subscribe(FailingHandler())

    bus.publish(make_event(identifier="evt-1"))
    bus.publish(make_event(identifier="evt-2"))

    assert [d.event.identifier for d in bus.dead_letters] == ["evt-1", "evt-2"]


# -- observability ----------------------------------------------------------- #


def test_event_published_recorded_once_per_publish() -> None:
    obs = InMemoryObservability()
    bus = InProcessEventBus(observability=obs)
    bus.subscribe(RecordingHandler())

    bus.publish(make_event())

    assert len(obs.events_of(InfraEventType.EVENT_PUBLISHED)) == 1


def test_event_published_recorded_even_without_subscribers() -> None:
    obs = InMemoryObservability()
    bus = InProcessEventBus(observability=obs)

    bus.publish(make_event())

    assert len(obs.events_of(InfraEventType.EVENT_PUBLISHED)) == 1
    assert obs.events_of(InfraEventType.EVENT_DELIVERED) == ()


def test_event_delivered_recorded_per_successful_delivery() -> None:
    obs = InMemoryObservability()
    bus = InProcessEventBus(observability=obs)
    bus.subscribe(RecordingHandler())
    bus.subscribe(RecordingHandler())

    bus.publish(make_event())

    delivered = obs.events_of(InfraEventType.EVENT_DELIVERED)
    assert len(delivered) == 2
    assert obs.counters["event_bus.delivered"] == 2


def test_delivered_subject_is_the_event_identifier() -> None:
    obs = InMemoryObservability()
    bus = InProcessEventBus(observability=obs)
    bus.subscribe(RecordingHandler())

    bus.publish(make_event(identifier="evt-42"))

    (delivered,) = obs.events_of(InfraEventType.EVENT_DELIVERED)
    assert delivered.subject == "evt-42"


def test_handler_failed_and_dead_lettered_recorded_on_failure() -> None:
    obs = InMemoryObservability()
    bus = InProcessEventBus(observability=obs)
    bus.subscribe(FailingHandler("nope"))

    bus.publish(make_event())

    failed = obs.events_of(InfraEventType.HANDLER_FAILED)
    dead_lettered = obs.events_of(InfraEventType.EVENT_DEAD_LETTERED)
    assert len(failed) == 1
    assert len(dead_lettered) == 1
    assert failed[0].detail["handler"] == "FailingHandler"
    assert "nope" in failed[0].detail["error"]
    assert obs.counters["event_bus.dead_lettered"] == 1
    # a failed delivery is not counted as delivered
    assert "event_bus.delivered" not in obs.counters


def test_mixed_success_and_failure_counters() -> None:
    obs = InMemoryObservability()
    bus = InProcessEventBus(observability=obs)
    bus.subscribe(RecordingHandler())
    bus.subscribe(FailingHandler())
    bus.subscribe(RecordingHandler())

    bus.publish(make_event())

    assert obs.counters["event_bus.delivered"] == 2
    assert obs.counters["event_bus.dead_lettered"] == 1
    assert len(obs.events_of(InfraEventType.EVENT_PUBLISHED)) == 1


def test_filtered_out_handler_records_no_delivery() -> None:
    obs = InMemoryObservability()
    bus = InProcessEventBus(observability=obs)
    bus.subscribe(RecordingHandler(), by_type("never.matches"))

    bus.publish(make_event(type="goal.created"))

    assert len(obs.events_of(InfraEventType.EVENT_PUBLISHED)) == 1
    assert obs.events_of(InfraEventType.EVENT_DELIVERED) == ()
    assert "event_bus.delivered" not in obs.counters
