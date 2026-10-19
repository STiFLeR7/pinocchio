"""Gemini invokers — the *wire* boundary that produces provider-shaped Gemini events.

The transport-shaped sub-layer (doc 22 §3, doc 23) for Google's Gemini CLI: it carries an
already-decided call and returns raw, **provider-vocabulary** events. It performs no Nexus
semantics — the :class:`~nexus_runtime_gemini.adapter.GeminiRuntimeAdapter` turns these raw
events into runtime-independent signals (semantic normalization). Two invokers ship, exactly
mirroring the Claude adapter's design (doc 03 §3 — provider logic lives only here):

* :class:`StubGeminiInvoker` — deterministic, subprocess-free; the CI/E2E path so the event
  stream is reproducible (the program's determinism requirement) without auth or network;
* :class:`GeminiCliInvoker` — shells to the real ``gemini`` CLI; the opt-in smoke path. Its
  output is non-deterministic by nature, so only the *shape* of the resulting event stream
  is asserted, never the model's text.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from nexus_execution.adapter import ExecutionControl


class RawGeminiKind(StrEnum):
    """The provider-vocabulary kind of a raw Gemini event (pre-normalization)."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    ARTIFACT = "artifact"
    RESULT = "result"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RawGeminiEvent:
    """One provider-shaped event from a Gemini invocation (still in Gemini vocabulary)."""

    kind: RawGeminiKind
    text: str = ""
    name: str | None = None
    exit_status: int | None = None
    is_error: bool = False
    data: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class GeminiInvoker(Protocol):
    """Produces the raw Gemini event stream for a rendered prompt (the wire)."""

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawGeminiEvent]:
        """Yield provider-shaped events for ``prompt`` until a terminal result/error."""
        ...


class StubGeminiInvoker:
    """A deterministic, subprocess-free Gemini stand-in for reproducible runs.

    The stream is a pure function of the rendered prompt — no clock, no randomness — so two
    runs of the same Work Package yield byte-identical event streams (and therefore
    identical ``runtime.*`` events under a fixed timestamp source). It models the *shape* of
    a real Gemini session: an assistant turn, one tool use, one produced artifact, a closing
    turn, then a normal result.
    """

    def __init__(self, *, fail: bool = False, hang: bool = False) -> None:
        self._fail = fail
        self._hang = hang

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawGeminiEvent]:
        digest = str(len(prompt))
        yield RawGeminiEvent(RawGeminiKind.TEXT, text=f"Planning response ({digest} chars).")
        yield RawGeminiEvent(
            RawGeminiKind.TOOL_USE, name="write_file", text="write_file(path=summary.md)"
        )
        yield RawGeminiEvent(
            RawGeminiKind.ARTIFACT, name="summary.md", text="", data={"path": "summary.md"}
        )
        if self._hang:
            # A cooperative, unbounded stream — the engine's cancel/timeout must stop it.
            while not control.cancelled:
                yield RawGeminiEvent(RawGeminiKind.TEXT, text="still generating…")
        yield RawGeminiEvent(RawGeminiKind.TEXT, text="Summary written.")
        if self._fail:
            yield RawGeminiEvent(
                RawGeminiKind.ERROR, text="model returned a safety refusal", is_error=True
            )
            return
        yield RawGeminiEvent(RawGeminiKind.RESULT, exit_status=0, text="done")


class GeminiCliInvoker:
    """Shells to the real ``gemini`` CLI (opt-in smoke path).

    Best-effort parser over the CLI's line stream. Cancellation terminates the process
    between lines (doc 09, graceful-then-forced). Kept deliberately small: it is exercised
    only by an opt-in smoke test that requires a real, authenticated ``gemini`` binary.
    """

    def __init__(self, *, binary: str = "gemini", extra_args: tuple[str, ...] = ()) -> None:
        self._binary = binary
        self._extra_args = extra_args

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawGeminiEvent]:
        args = [self._binary, "--prompt", prompt, "--output-format", "json", *self._extra_args]
        process = subprocess.Popen(
            args,
            cwd=working_dir or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
                yield RawGeminiEvent(
                    RawGeminiKind.ERROR,
                    text=f"gemini exited {process.returncode}",
                    is_error=True,
                    exit_status=process.returncode,
                )
        finally:
            if process.poll() is None:
                process.kill()


def _parse_cli_line(line: str) -> RawGeminiEvent | None:
    """Map one CLI output line onto a raw Gemini event (best-effort)."""
    line = line.strip()
    if not line:
        return None
    try:
        obj: dict[str, object] = json.loads(line)
    except json.JSONDecodeError:
        return RawGeminiEvent(RawGeminiKind.TEXT, text=line)
    kind = obj.get("type")
    if kind == "content":
        return RawGeminiEvent(RawGeminiKind.TEXT, text=_content_text(obj), data=obj)
    if kind == "tool_call":
        return RawGeminiEvent(RawGeminiKind.TOOL_USE, name=str(obj.get("name", "tool")), data=obj)
    if kind == "finish":
        if bool(obj.get("is_error", False)):
            return RawGeminiEvent(
                RawGeminiKind.ERROR, text=str(obj.get("reason", "error")), is_error=True, data=obj
            )
        return RawGeminiEvent(
            RawGeminiKind.RESULT, exit_status=0, text=str(obj.get("reason", "success")), data=obj
        )
    return RawGeminiEvent(RawGeminiKind.TEXT, text=str(kind), data=obj)


def _content_text(obj: dict[str, object]) -> str:
    """Extract text from a ``content`` event (best-effort over the CLI's shape)."""
    text = obj.get("text")
    return text if isinstance(text, str) else ""
