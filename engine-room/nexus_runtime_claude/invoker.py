"""Claude invokers — the *wire* boundary that produces provider-shaped Claude events.

This is the transport-shaped sub-layer (doc 22 §3, doc 23): it carries an already-decided
call to Claude Code and returns raw, **provider-vocabulary** events. It performs no Nexus
semantics — the :class:`~nexus_runtime_claude.adapter.ClaudeRuntimeAdapter` turns these raw
events into runtime-independent signals (semantic normalization). Two invokers ship:

* :class:`StubClaudeInvoker` — deterministic, subprocess-free; the CI/E2E path so the event
  stream is reproducible (the program's determinism requirement) without auth or network;
* :class:`ClaudeCliInvoker` — shells to the real ``claude`` CLI in ``--output-format
  stream-json`` mode; the opt-in smoke path. Its output is non-deterministic by nature, so
  only the *shape* of the resulting event stream is asserted, never the model's text.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from nexus_execution.adapter import ExecutionControl


class RawClaudeKind(StrEnum):
    """The provider-vocabulary kind of a raw Claude event (pre-normalization)."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    ARTIFACT = "artifact"
    RESULT = "result"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RawClaudeEvent:
    """One provider-shaped event from a Claude invocation (still in Claude vocabulary)."""

    kind: RawClaudeKind
    text: str = ""
    name: str | None = None
    exit_status: int | None = None
    is_error: bool = False
    data: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class ClaudeInvoker(Protocol):
    """Produces the raw Claude event stream for a rendered prompt (the wire)."""

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawClaudeEvent]:
        """Yield provider-shaped events for ``prompt`` until a terminal result/error."""
        ...


class StubClaudeInvoker:
    """A deterministic, subprocess-free Claude stand-in for reproducible runs.

    The stream is a pure function of the rendered prompt — no clock, no randomness — so two
    runs of the same Work Package yield byte-identical event streams (and therefore
    identical ``runtime.*`` events under a fixed timestamp source). It models the *shape* of
    a real Claude session: a couple of assistant turns, one tool use, one produced artifact,
    then a normal result.
    """

    def __init__(self, *, fail: bool = False, hang: bool = False) -> None:
        self._fail = fail
        self._hang = hang

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawClaudeEvent]:
        digest = str(len(prompt))
        yield RawClaudeEvent(RawClaudeKind.TEXT, text=f"Analyzing task ({digest} chars).")
        yield RawClaudeEvent(
            RawClaudeKind.TOOL_USE, name="edit_file", text="edit_file(path=main.py)"
        )
        yield RawClaudeEvent(
            RawClaudeKind.ARTIFACT, name="main.py", text="", data={"path": "main.py"}
        )
        if self._hang:
            # A cooperative, unbounded stream — the engine's cancel/timeout must stop it.
            while not control.cancelled:
                yield RawClaudeEvent(RawClaudeKind.TEXT, text="still working…")
        yield RawClaudeEvent(RawClaudeKind.TEXT, text="Applied the formatting fix.")
        if self._fail:
            yield RawClaudeEvent(
                RawClaudeKind.ERROR, text="model reported an execution error", is_error=True
            )
            return
        yield RawClaudeEvent(RawClaudeKind.RESULT, exit_status=0, text="done")


class ClaudeCliInvoker:
    """Shells to the real ``claude`` CLI in ``stream-json`` mode (opt-in smoke path).

    Best-effort parser over the CLI's JSONL stream. Cancellation terminates the process
    between lines (doc 09, graceful-then-forced). Kept deliberately small: it is exercised
    only by an opt-in smoke test that requires a real, authenticated ``claude`` binary.
    """

    def __init__(self, *, binary: str = "claude", extra_args: tuple[str, ...] = ()) -> None:
        self._binary = binary
        self._extra_args = extra_args

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawClaudeEvent]:
        args = [
            self._binary,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            *self._extra_args,
        ]
        process = subprocess.Popen(
            args,
            cwd=working_dir or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                if control.cancelled:
                    process.terminate()
                    return
                event = _parse_cli_line(line)
                if event is not None:
                    yield event
            process.wait()
            if process.returncode not in (0, None):
                yield RawClaudeEvent(
                    RawClaudeKind.ERROR,
                    text=f"claude exited {process.returncode}",
                    is_error=True,
                    exit_status=process.returncode,
                )
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.poll() is None:
                process.kill()
            process.wait()


def _parse_cli_line(line: str) -> RawClaudeEvent | None:
    """Map one ``stream-json`` line onto a raw Claude event (best-effort)."""
    line = line.strip()
    if not line:
        return None
    try:
        obj: dict[str, object] = json.loads(line)
    except json.JSONDecodeError:
        return RawClaudeEvent(RawClaudeKind.TEXT, text=line)
    kind = obj.get("type")
    if kind == "assistant":
        return RawClaudeEvent(RawClaudeKind.TEXT, text=_assistant_text(obj), data=obj)
    if kind == "result":
        is_error = bool(obj.get("is_error", False))
        if is_error:
            return RawClaudeEvent(
                RawClaudeKind.ERROR, text=str(obj.get("subtype", "error")), is_error=True, data=obj
            )
        return RawClaudeEvent(
            RawClaudeKind.RESULT, exit_status=0, text=str(obj.get("subtype", "success")), data=obj
        )
    return RawClaudeEvent(RawClaudeKind.TEXT, text=str(kind), data=obj)


def _assistant_text(obj: dict[str, object]) -> str:
    """Extract concatenated assistant text from a ``stream-json`` assistant event."""
    message = obj.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)
