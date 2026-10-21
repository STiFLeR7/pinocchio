"""LLM invokers — the *wire* boundary that produces provider-shaped LLM events.

This is the transport-shaped sub-layer (doc 22 §3, doc 23), the same role
``nexus_runtime_claude.invoker`` plays for Claude Code: it carries an already-decided call to a
real LLM provider and returns raw, provider-vocabulary events. It performs no Nexus semantics —
:class:`~nexus_runtime_llm.adapter.LLMRuntimeAdapter` turns these raw events into
runtime-independent signals (semantic normalization). Unlike the CLI-shelling adapters
(``nexus_runtime_claude``/``nexus_runtime_gemini``), every non-stub invoker here calls a real
provider HTTP API directly via ``httpx`` (already a platform dependency) — no subprocess, no new
SDK dependency per provider.

Four invokers ship:

* :class:`StubLLMInvoker` — deterministic, network-free; the production-safe default every other
  runtime adapter in this platform also defaults to, so nothing calls a real API by accident;
* :class:`AnthropicInvoker` — the real Anthropic Messages API (streaming via SSE);
* :class:`OpenAICompatibleInvoker` — the real OpenAI Chat Completions wire shape (streaming via
  SSE), reused unmodified for both OpenAI and OpenRouter (OpenRouter is OpenAI-API-compatible —
  v1's own ``OpenRouterClient`` made the same observation);
* :class:`GeminiInvoker` — the real Gemini ``generateContent`` REST API (non-streaming; Gemini's
  streaming wire shape is not implemented in this vertical slice, disclosed rather than faked).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

import httpx

from nexus_execution.adapter import ExecutionControl

_DEFAULT_TIMEOUT_SECONDS = 60.0


class RawLLMKind(StrEnum):
    """The provider-vocabulary kind of a raw LLM event (pre-normalization)."""

    TEXT = "text"
    RESULT = "result"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RawLLMEvent:
    """One provider-shaped event from an LLM invocation (still in provider vocabulary)."""

    kind: RawLLMKind
    text: str = ""
    exit_status: int | None = None
    is_transport_fault: bool = False
    """Set on :attr:`RawLLMKind.ERROR` when the fault is a wire/connection failure, not a
    provider-reported error — lets the adapter map it onto the correct doc-11 error class
    (``TransportError`` vs ``ProviderError``) instead of collapsing every failure into one class."""
    data: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class LLMInvoker(Protocol):
    """Produces the raw LLM event stream for a rendered prompt (the wire)."""

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawLLMEvent]:
        """Yield provider-shaped events for ``prompt`` until a terminal result/error."""
        ...


class StubLLMInvoker:
    """A deterministic, network-free LLM stand-in for reproducible runs.

    Mirrors ``StubClaudeInvoker``: the stream is a pure function of the rendered prompt — no
    clock, no randomness, no network — so replay and testing never depend on a real provider
    being reachable, authenticated, or deterministic. This is the adapter's default invoker.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawLLMEvent]:
        digest = str(len(prompt))
        yield RawLLMEvent(RawLLMKind.TEXT, text=f"[stub reasoning over {digest} chars]\n")
        if self._fail:
            yield RawLLMEvent(RawLLMKind.ERROR, text="stub-configured failure")
            return
        yield RawLLMEvent(RawLLMKind.RESULT, exit_status=0, text="done")


class AnthropicInvoker:
    """Drives the real Anthropic Messages API (``POST /v1/messages``, SSE streaming)."""

    _API_VERSION = "2023-06-01"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int = 1024,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = base_url
        self._timeout = timeout

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawLLMEvent]:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._API_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            with (
                httpx.Client(timeout=self._timeout) as client,
                client.stream(
                    "POST", f"{self._base_url}/messages", headers=headers, json=body
                ) as response,
            ):
                if response.status_code >= 400:
                    detail = _read_error_body(response)
                    yield RawLLMEvent(
                        RawLLMKind.ERROR, text=f"anthropic {response.status_code}: {detail}"
                    )
                    return
                for raw_event in _iter_sse_events(response):
                    if control.cancelled:
                        return
                    event_type = raw_event.get("type")
                    if event_type == "content_block_delta":
                        delta = raw_event.get("delta", {})
                        text = delta.get("text") if isinstance(delta, dict) else None
                        if isinstance(text, str) and text:
                            yield RawLLMEvent(RawLLMKind.TEXT, text=text)
                    elif event_type == "message_stop":
                        yield RawLLMEvent(RawLLMKind.RESULT, exit_status=0, text="done")
                        return
                    elif event_type == "error":
                        message = raw_event.get("error", {})
                        error_detail: object = (
                            message.get("message") if isinstance(message, dict) else message
                        )
                        yield RawLLMEvent(RawLLMKind.ERROR, text=str(error_detail))
                        return
        except httpx.TransportError as exc:
            yield RawLLMEvent(RawLLMKind.ERROR, text=str(exc), is_transport_fault=True)


class OpenAICompatibleInvoker:
    """Drives an OpenAI-shaped Chat Completions API (``POST /chat/completions``, SSE streaming).

    Reused unmodified for OpenAI and OpenRouter — both speak the same wire shape; only
    ``base_url``/``api_key``/``model`` differ (the same observation v1's own multi-provider
    ``OpenRouterClient`` made in production).
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        max_tokens: int = 1024,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._max_tokens = max_tokens
        self._timeout = timeout

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawLLMEvent]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        body = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            with (
                httpx.Client(timeout=self._timeout) as client,
                client.stream(
                    "POST", f"{self._base_url}/chat/completions", headers=headers, json=body
                ) as response,
            ):
                if response.status_code >= 400:
                    detail = _read_error_body(response)
                    yield RawLLMEvent(RawLLMKind.ERROR, text=f"{response.status_code}: {detail}")
                    return
                for raw_event in _iter_sse_events(response):
                    if control.cancelled:
                        return
                    if raw_event.get("_raw") == "[DONE]":
                        yield RawLLMEvent(RawLLMKind.RESULT, exit_status=0, text="done")
                        return
                    choices = raw_event.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                    text = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(text, str) and text:
                        yield RawLLMEvent(RawLLMKind.TEXT, text=text)
                    finish_reason = (
                        choices[0].get("finish_reason") if isinstance(choices[0], dict) else None
                    )
                    if finish_reason is not None:
                        yield RawLLMEvent(RawLLMKind.RESULT, exit_status=0, text="done")
                        return
        except httpx.TransportError as exc:
            yield RawLLMEvent(RawLLMKind.ERROR, text=str(exc), is_transport_fault=True)


class GeminiInvoker:
    """Drives the real Gemini ``generateContent`` REST API (non-streaming — disclosed scope limit)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawLLMEvent]:
        url = f"{self._base_url}/models/{self._model}:generateContent"
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers={"x-goog-api-key": self._api_key}, json=body)
            if response.status_code >= 400:
                yield RawLLMEvent(
                    RawLLMKind.ERROR, text=f"gemini {response.status_code}: {response.text}"
                )
                return
            if control.cancelled:
                return
            payload = response.json()
            text = _extract_gemini_text(payload)
            if text:
                yield RawLLMEvent(RawLLMKind.TEXT, text=text)
            yield RawLLMEvent(RawLLMKind.RESULT, exit_status=0, text="done")
        except httpx.TransportError as exc:
            yield RawLLMEvent(RawLLMKind.ERROR, text=str(exc), is_transport_fault=True)


def _extract_gemini_text(payload: dict[str, object]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return ""
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


def _read_error_body(response: httpx.Response) -> str:
    try:
        response.read()
        return response.text[:500]
    except httpx.HTTPError:
        return "<unreadable error body>"


def _iter_sse_events(response: httpx.Response) -> Iterator[dict[str, object]]:
    """Parse a ``text/event-stream`` body into ``data:`` JSON payloads (or a ``[DONE]`` marker)."""
    for line in response.iter_lines():
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            yield {"_raw": "[DONE]"}
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            yield parsed
