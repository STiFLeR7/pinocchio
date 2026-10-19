"""Versioned, deterministic serialization.

Two concerns live here:

- :class:`VersionedSerializer` implements ``nexus_core.persistence.Serializer``:
  it wraps a domain object in a small envelope that records an explicit schema
  version, so stored data can evolve forward/backward-compatibly. Round-tripping
  is identity-preserving.
- :func:`canonical_json` / :func:`content_hash` give a deterministic byte image
  of any value, used for snapshot integrity validation. Determinism here means:
  the same logical value always produces the same bytes (keys sorted, no
  incidental whitespace, enums by value).

No transport protocol is introduced — this is structural (de)serialization only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ValidationError

from nexus_infra.errors import IntegrityError

ENVELOPE_VERSION_KEY = "schema_version"
ENVELOPE_TYPE_KEY = "type"
ENVELOPE_DATA_KEY = "data"

DEFAULT_SCHEMA_VERSION = "1"


def _normalize(value: Any) -> Any:
    """Recursively convert ``value`` into JSON-native, ordering-stable primitives."""
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    """A deterministic JSON string for ``value`` (sorted keys, compact)."""
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    """A stable SHA-256 hex digest of ``value``'s canonical image."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class VersionedSerializer:
    """Envelope-based serializer implementing ``Serializer`` (format-agnostic).

    The envelope is ``{schema_version, type, data}``. ``data`` is the object's
    structural dump; the version makes schema evolution explicit. Deserialization
    accepts either an envelope or a bare object dump (backward compatibility with
    unversioned data, where practical).
    """

    def __init__(self, schema_version: str = DEFAULT_SCHEMA_VERSION) -> None:
        self._version = schema_version

    def serialize(self, obj: BaseModel) -> Mapping[str, Any]:
        return {
            ENVELOPE_VERSION_KEY: self._version,
            ENVELOPE_TYPE_KEY: type(obj).__name__,
            ENVELOPE_DATA_KEY: obj.model_dump(mode="json"),
        }

    def deserialize[M: BaseModel](self, model_type: type[M], data: Mapping[str, Any]) -> M:
        payload = data.get(ENVELOPE_DATA_KEY, data)
        try:
            return model_type.model_validate(dict(payload))
        except ValidationError as exc:
            raise IntegrityError(f"failed to deserialize {model_type.__name__}: {exc}") from exc
