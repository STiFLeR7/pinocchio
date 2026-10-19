"""Unit tests for nexus_runtime_gemini.invoker — the wire boundary + CLI parser.

The deterministic stub is exercised directly; the real-CLI invoker is exercised with a
monkeypatched ``subprocess.Popen`` (no real ``gemini`` binary), so every branch — normal
stream, non-zero exit, mid-stream cancellation, and the kill-on-teardown finally — is covered
deterministically. The line parser is unit-tested case by case.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from nexus_execution.adapter import ExecutionControl
from nexus_runtime_gemini import invoker as invoker_module
from nexus_runtime_gemini.invoker import (
    GeminiCliInvoker,
    RawGeminiEvent,
    RawGeminiKind,
    StubGeminiInvoker,
    _content_text,
    _parse_cli_line,
)


def _collect(
    invoker: StubGeminiInvoker, *, control: ExecutionControl | None = None
) -> list[RawGeminiEvent]:
    return list(
        invoker.invoke(
            prompt="do the thing", working_dir=".", control=control or ExecutionControl()
        )
    )


# StubGeminiInvoker --------------------------------------------------------- #


def test_stub_is_deterministic() -> None:
    assert _collect(StubGeminiInvoker()) == _collect(StubGeminiInvoker())


def test_stub_ends_with_result() -> None:
    events = _collect(StubGeminiInvoker())
    assert events[-1].kind is RawGeminiKind.RESULT
    assert events[-1].exit_status == 0


def test_stub_emits_tool_and_artifact() -> None:
    kinds = [e.kind for e in _collect(StubGeminiInvoker())]
    assert RawGeminiKind.TOOL_USE in kinds
    assert RawGeminiKind.ARTIFACT in kinds


def test_stub_fail_mode_ends_with_error() -> None:
    events = _collect(StubGeminiInvoker(fail=True))
    assert events[-1].kind is RawGeminiKind.ERROR
    assert events[-1].is_error is True


def test_stub_hang_mode_stops_on_cancel() -> None:
    invoker = StubGeminiInvoker(hang=True)
    control = ExecutionControl()
    collected: list[RawGeminiEvent] = []
    for event in invoker.invoke(prompt="p", working_dir=".", control=control):
        collected.append(event)
        if len(collected) >= 5:
            control.cancel()
        if len(collected) >= 12:  # safety net
            break
    assert len(collected) < 12


# CLI line parser ----------------------------------------------------------- #


def test_parse_empty_line_is_none() -> None:
    assert _parse_cli_line("   ") is None


def test_parse_non_json_is_text() -> None:
    event = _parse_cli_line("not json")
    assert event is not None
    assert event.kind is RawGeminiKind.TEXT
    assert event.text == "not json"


def test_parse_content_event() -> None:
    event = _parse_cli_line('{"type":"content","text":"hello"}')
    assert event is not None
    assert event.kind is RawGeminiKind.TEXT
    assert event.text == "hello"


def test_parse_tool_call_event() -> None:
    event = _parse_cli_line('{"type":"tool_call","name":"write_file"}')
    assert event is not None
    assert event.kind is RawGeminiKind.TOOL_USE
    assert event.name == "write_file"


def test_parse_finish_success() -> None:
    event = _parse_cli_line('{"type":"finish","reason":"stop","is_error":false}')
    assert event is not None
    assert event.kind is RawGeminiKind.RESULT


def test_parse_finish_error() -> None:
    event = _parse_cli_line('{"type":"finish","reason":"safety","is_error":true}')
    assert event is not None
    assert event.kind is RawGeminiKind.ERROR
    assert event.is_error is True


def test_parse_unknown_type_is_text() -> None:
    event = _parse_cli_line('{"type":"system"}')
    assert event is not None
    assert event.kind is RawGeminiKind.TEXT


def test_content_text_handles_missing_text() -> None:
    assert _content_text({"type": "content"}) == ""


def test_content_text_handles_non_string_text() -> None:
    assert _content_text({"text": 123}) == ""


# GeminiCliInvoker with a monkeypatched Popen ------------------------------- #


class _FakePopen:
    def __init__(
        self, lines: list[str], *, returncode: int = 0, stay_running: bool = False
    ) -> None:
        self.stdout: Iterator[str] = iter(lines)
        self.stderr = None
        self.returncode = returncode
        self._stay_running = stay_running
        self.terminated = False
        self.killed = False
        self._waited = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self) -> int:
        self._waited = True
        return self.returncode

    def poll(self) -> int | None:
        if self._stay_running and not self._waited:
            return None
        return self.returncode

    def kill(self) -> None:
        self.killed = True


def _patch_popen(monkeypatch: pytest.MonkeyPatch, popen: _FakePopen) -> None:
    def factory(*_args: Any, **_kwargs: Any) -> _FakePopen:
        return popen

    monkeypatch.setattr(invoker_module.subprocess, "Popen", factory)


def test_cli_invoker_streams_and_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [
        '{"type":"content","text":"hi"}\n',
        "   \n",  # blank line → parsed to None → skipped
        '{"type":"finish","reason":"stop","is_error":false}\n',
    ]
    _patch_popen(monkeypatch, _FakePopen(lines, returncode=0))
    events = list(GeminiCliInvoker().invoke(prompt="p", working_dir="", control=ExecutionControl()))
    assert events[0].kind is RawGeminiKind.TEXT
    assert events[-1].kind is RawGeminiKind.RESULT


def test_cli_invoker_reports_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_popen(monkeypatch, _FakePopen(["plain output\n"], returncode=2))
    events = list(
        GeminiCliInvoker().invoke(prompt="p", working_dir=".", control=ExecutionControl())
    )
    assert events[-1].kind is RawGeminiKind.ERROR
    assert events[-1].exit_status == 2


def test_cli_invoker_cancels_and_kills(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = _FakePopen(["a\n", "b\n", "c\n"], stay_running=True)
    _patch_popen(monkeypatch, popen)
    control = ExecutionControl()
    control.cancel()  # cancelled before first line is consumed
    events = list(GeminiCliInvoker().invoke(prompt="p", working_dir=".", control=control))
    assert events == []
    assert popen.terminated is True
    assert popen.killed is True  # finally: poll() is None → kill
