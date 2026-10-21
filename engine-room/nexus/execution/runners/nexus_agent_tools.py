"""Structured tool-call contract for the Nexus agent loop (H-2 / Track H).

Replaces brittle free-text parsing with a schema-validated tool-call so a malformed model completion
becomes an explicit error state — never a silent ``finish`` masquerading as success (AP-105 Gap 6).
No new tools are introduced: the recognized set is exactly the existing five.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

#: The recognized tool names — the existing five, no additions (capability-model §3).
VALID_TOOLS: frozenset[str] = frozenset(
    {"web_search", "read_file", "write_file", "execute_command", "finish"}
)


class ToolCall(BaseModel):
    """A validated structured tool-call emitted by the model."""

    thought: str = ""
    tool_name: str
    tool_arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallParseError(Exception):
    """Raised when a completion is not a valid, recognized structured tool-call (fail-honest)."""


def extract_json_block(text: str) -> str:
    """Extract the JSON payload from a model completion, tolerating ``` and ```json fences."""
    s = text.strip()
    if "```json" in s:
        s = s.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in s:
        s = s.split("```", 1)[1].split("```", 1)[0].strip()
    return s


def parse_tool_call(completion: str) -> ToolCall:
    """Parse and validate a structured tool-call, raising ``ToolCallParseError`` on any violation.

    A malformed payload, a non-object, an invalid schema, or an unrecognized tool name all raise —
    the caller must treat this as a real error, not a completion.
    """
    block = extract_json_block(completion)
    try:
        data = json.loads(block)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ToolCallParseError(f"Completion is not valid JSON: {exc!s}") from exc

    if not isinstance(data, dict):
        raise ToolCallParseError("Tool call must be a JSON object.")

    try:
        call = ToolCall(**data)
    except ValidationError as exc:
        raise ToolCallParseError(f"Invalid tool-call schema: {exc!s}") from exc

    if call.tool_name not in VALID_TOOLS:
        raise ToolCallParseError(
            f"Unknown tool '{call.tool_name}'. Recognized tools: {sorted(VALID_TOOLS)}."
        )
    return call
