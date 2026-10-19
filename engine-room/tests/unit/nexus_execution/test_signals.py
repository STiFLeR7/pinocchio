"""Unit tests for nexus_execution.signals — the provider-independent signal value types."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    ProgressSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)


def test_stream_channel_values() -> None:
    assert StreamChannel.STDOUT == "stdout"
    assert StreamChannel.STDERR == "stderr"
    assert StreamChannel.STRUCTURED == "structured"


def test_terminal_outcome_values() -> None:
    assert TerminalOutcome.COMPLETED == "completed"
    assert TerminalOutcome.FAILED == "failed"
    assert TerminalOutcome.CANCELLED == "cancelled"


def test_output_signal_carries_channel_and_text() -> None:
    signal = OutputSignal(channel=StreamChannel.STDOUT, text="hi")
    assert signal.channel is StreamChannel.STDOUT
    assert signal.text == "hi"


def test_progress_signal_defaults_to_unknown_fraction() -> None:
    signal = ProgressSignal(phase="p")
    assert signal.fraction is None
    assert signal.milestone is None


def test_artifact_signal_holds_reference_by_id() -> None:
    ref = Reference(target_type="artifact", identifier="a")
    signal = ArtifactSignal(artifact_ref=ref, kind="file")
    assert signal.artifact_ref.identifier == "a"
    assert signal.kind == "file"


def test_terminal_signal_defaults() -> None:
    signal = TerminalSignal(TerminalOutcome.COMPLETED)
    assert signal.exit_status is None
    assert signal.detail is None
    assert signal.error_class is None


def test_signals_are_frozen() -> None:
    import dataclasses

    signal = OutputSignal(StreamChannel.STDOUT, "x")
    try:
        signal.text = "y"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("signal should be frozen")
