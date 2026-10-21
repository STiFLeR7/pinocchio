"""Unit tests for nexus_runtime_claude.invoker — the wire boundary + CLI parser.

The deterministic stub is exercised directly; the real-CLI invoker is exercised with a
monkeypatched ``subprocess.Popen`` (no real ``claude`` binary), so every branch — normal
stream, non-zero exit, mid-stream cancellation, and the kill-on-teardown finally — is
covered deterministically. The JSONL parser is unit-tested line by line.
"""

from __future__ import annotations

import io
import subprocess
from typing import Any

import pytest

from nexus_execution.adapter import ExecutionControl
from nexus_runtime_claude.invoker import (
    ClaudeCliInvoker,
    RawClaudeEvent,
    RawClaudeKind,
    StubClaudeInvoker,
    _assistant_text,
    _parse_cli_line,
)

# --------------------------------------------------------------------------- #
# StubClaudeInvoker                                                              #
# --------------------------------------------------------------------------- #


def _collect(
    invoker: StubClaudeInvoker, *, control: ExecutionControl | None = None
) -> list[RawClaudeEvent]:
    return list(
        invoker.invoke(
            prompt="do the thing", working_dir=".", control=control or ExecutionControl()
        )
    )


def test_stub_is_deterministic() -> None:
    assert _collect(StubClaudeInvoker()) == _collect(StubClaudeInvoker())


def test_stub_ends_with_result() -> None:
    events = _collect(StubClaudeInvoker())
    assert events[-1].kind is RawClaudeKind.RESULT
    assert events[-1].exit_status == 0


def test_stub_emits_tool_and_artifact() -> None:
    kinds = [e.kind for e in _collect(StubClaudeInvoker())]
    assert RawClaudeKind.TOOL_USE in kinds
    assert RawClaudeKind.ARTIFACT in kinds


def test_stub_fail_mode_ends_with_error() -> None:
    events = _collect(StubClaudeInvoker(fail=True))
    assert events[-1].kind is RawClaudeKind.ERROR
    assert events[-1].is_error is True


def test_stub_hang_mode_stops_on_cancel() -> None:
    invoker = StubClaudeInvoker(hang=True)
    control = ExecutionControl()
    collected: list[RawClaudeEvent] = []
    for event in invoker.invoke(prompt="p", working_dir=".", control=control):
        collected.append(event)
        if len(collected) >= 5:
            control.cancel()
        if len(collected) >= 12:  # safety net
            break
    # The hang loop must have exited once cancelled (well before the safety net).
    assert len(collected) < 12


# --------------------------------------------------------------------------- #
# CLI JSONL parser                                                              #
# --------------------------------------------------------------------------- #


def test_parse_empty_line_is_none() -> None:
    assert _parse_cli_line("   ") is None


def test_parse_non_json_is_text() -> None:
    event = _parse_cli_line("not json")
    assert event is not None
    assert event.kind is RawClaudeKind.TEXT
    assert event.text == "not json"


def test_parse_assistant_event() -> None:
    line = '{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}'
    event = _parse_cli_line(line)
    assert event is not None
    assert event.kind is RawClaudeKind.TEXT
    assert event.text == "hello"


def test_parse_result_success() -> None:
    event = _parse_cli_line('{"type":"result","subtype":"success","is_error":false}')
    assert event is not None
    assert event.kind is RawClaudeKind.RESULT


def test_parse_result_error() -> None:
    event = _parse_cli_line('{"type":"result","subtype":"error_max_turns","is_error":true}')
    assert event is not None
    assert event.kind is RawClaudeKind.ERROR
    assert event.is_error is True


def test_parse_unknown_type_is_text() -> None:
    event = _parse_cli_line('{"type":"system","subtype":"init"}')
    assert event is not None
    assert event.kind is RawClaudeKind.TEXT


def test_assistant_text_handles_missing_message() -> None:
    assert _assistant_text({"type": "assistant"}) == ""


def test_assistant_text_handles_non_list_content() -> None:
    assert _assistant_text({"message": {"content": "oops"}}) == ""


def test_assistant_text_skips_non_text_blocks() -> None:
    obj: dict[str, object] = {
        "message": {"content": [{"type": "tool_use", "name": "x"}, {"type": "text", "text": "hi"}]}
    }
    assert _assistant_text(obj) == "hi"


def test_assistant_text_skips_text_block_with_non_string_text() -> None:
    # A "text" block whose text is not a str must be skipped, not appended.
    obj: dict[str, object] = {
        "message": {"content": [{"type": "text", "text": 123}, {"type": "text", "text": "ok"}]}
    }
    assert _assistant_text(obj) == "ok"


# --------------------------------------------------------------------------- #
# ClaudeCliInvoker with a monkeypatched Popen                                    #
# --------------------------------------------------------------------------- #


class _FakePopen:
    def __init__(
        self, lines: list[str], *, returncode: int = 0, stay_running: bool = False
    ) -> None:
        self.stdout = io.StringIO("".join(lines))
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

    monkeypatch.setattr(subprocess, "Popen", factory)


def test_cli_invoker_streams_and_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [
        '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}\n',
        "   \n",  # blank line → parsed to None → skipped (not yielded)
        '{"type":"result","subtype":"success","is_error":false}\n',
    ]
    popen = _FakePopen(lines, returncode=0)
    _patch_popen(monkeypatch, popen)
    events = list(ClaudeCliInvoker().invoke(prompt="p", working_dir="", control=ExecutionControl()))
    assert events[0].kind is RawClaudeKind.TEXT
    assert events[-1].kind is RawClaudeKind.RESULT
    assert popen.stdout.closed
    assert popen._waited


def test_cli_invoker_uses_robust_utf8_and_does_not_pipe_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    popen = _FakePopen(
        ['{"type":"assistant","message":{"content":[{"type":"text","text":"café"}]}}\n']
    )
    received: dict[str, Any] = {}

    def factory(*args: Any, **kwargs: Any) -> _FakePopen:
        received.update(kwargs)
        return popen

    monkeypatch.setattr(subprocess, "Popen", factory)
    events = list(
        ClaudeCliInvoker().invoke(prompt="p", working_dir=".", control=ExecutionControl())
    )

    assert events[0].text == "café"
    assert received["encoding"] == "utf-8"
    assert received["errors"] == "replace"
    assert received["stderr"] == subprocess.DEVNULL


def test_cli_invoker_reports_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_popen(monkeypatch, _FakePopen(["plain output\n"], returncode=2))
    events = list(
        ClaudeCliInvoker().invoke(prompt="p", working_dir=".", control=ExecutionControl())
    )
    assert events[-1].kind is RawClaudeKind.ERROR
    assert events[-1].exit_status == 2


def test_cli_invoker_cancels_and_kills(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = _FakePopen(["a\n", "b\n", "c\n"], stay_running=True)
    _patch_popen(monkeypatch, popen)
    control = ExecutionControl()
    control.cancel()  # cancelled before first line is consumed
    events = list(ClaudeCliInvoker().invoke(prompt="p", working_dir=".", control=control))
    assert events == []
    assert popen.terminated is True
    assert popen.killed is True  # finally: poll() is None → kill
    assert popen.stdout.closed
    assert popen._waited


def test_cli_invoker_reaps_and_closes_on_stream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = _FakePopen(["malformed-but-text\n"], stay_running=True)
    _patch_popen(monkeypatch, popen)

    def parse_error(_line: str) -> None:
        raise RuntimeError("simulated parser error")

    monkeypatch.setattr("nexus_runtime_claude.invoker._parse_cli_line", parse_error)
    with pytest.raises(RuntimeError, match="simulated parser error"):
        list(ClaudeCliInvoker().invoke(prompt="p", working_dir=".", control=ExecutionControl()))

    assert popen.stdout.closed
    assert popen.killed
    assert popen._waited
