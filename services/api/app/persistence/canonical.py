"""Canonical JSON: the single serialisation used for stored payloads and hashes."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain(v) for v in value]
    return value


def canonical_json(model: BaseModel | Mapping[str, Any] | Sequence[Any]) -> str:
    """Sorted keys, compact separators, UTF-8 kept as is; NaN and Infinity are rejected."""
    return json.dumps(
        _plain(model), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
