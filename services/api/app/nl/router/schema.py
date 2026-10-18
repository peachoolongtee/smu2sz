"""The strict JSON Schema subset the router validates a model's slots against (ADR-0015), and the wire schema it sends.

A tool's `slots_schema` is a flat object schema. The keywords allowed are the ones below; `check_schema` refuses any other, so a
tool cannot rely on a constraint that would silently not be checked. Validation is strict: no type coercion (a bool is not an
integer, "30" is not 30), no unknown property, every `required` property present, numbers inside their range, strings inside
their length and enum. `wire_schema` is the same shape without the numeric and length bounds, which providers' structured-output
modes do not accept; the bounds are enforced here, on what comes back.
"""

from __future__ import annotations

import math
import re
from typing import Any

OBJECT_KEYS = frozenset({"type", "properties", "required", "additionalProperties", "description"})
VALUE_KEYS = frozenset({"type", "description", "enum", "minimum", "maximum", "minLength", "maxLength", "pattern"})
TYPES = frozenset({"string", "integer", "number", "boolean", "null"})
_BOUNDS = ("minimum", "maximum", "minLength", "maxLength", "pattern")


class SchemaError(ValueError):
    """A tool's slot schema uses something the router does not validate."""


def _types(spec: dict[str, Any]) -> list[str]:
    t = spec.get("type")
    return [t] if isinstance(t, str) else list(t) if isinstance(t, list) else []


def check_schema(schema: dict[str, Any], where: str = "") -> None:
    """Raise SchemaError unless `schema` is a flat object schema in the subset."""
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise SchemaError(f"{where}: the slots schema must be an object schema")
    if extra := set(schema) - OBJECT_KEYS:
        raise SchemaError(f"{where}: unsupported keywords {sorted(extra)}")
    if schema.get("additionalProperties") is not False:
        raise SchemaError(f"{where}: additionalProperties must be false")
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        raise SchemaError(f"{where}: properties must be an object")
    for name in schema.get("required", []):
        if name not in props:
            raise SchemaError(f"{where}: required {name!r} is not a property")
    for name, spec in props.items():
        if not isinstance(spec, dict) or (extra := set(spec) - VALUE_KEYS):
            raise SchemaError(f"{where}.{name}: unsupported keywords {sorted(extra) if isinstance(spec, dict) else spec}")
        ts = _types(spec)
        if not ts or not set(ts) <= TYPES:
            raise SchemaError(f"{where}.{name}: type must be one of {sorted(TYPES)}")
        if "enum" in spec and not (isinstance(spec["enum"], list) and spec["enum"]):
            raise SchemaError(f"{where}.{name}: enum must be a non-empty list")
        if "pattern" in spec:
            re.compile(spec["pattern"])


def _is(value: Any, t: str) -> bool:
    if t == "null":
        return value is None
    if t == "boolean":
        return isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    if t == "string":
        return isinstance(value, str)
    return False


def coded_problems(schema: dict[str, Any], value: Any) -> list[tuple[str, str]]:
    """(reason code, message) for each way `value` does not satisfy `schema` (empty when it does). The code is fixed
    (unknown_slot, missing_slot, wrong_type, bad_value, out_of_range, malformed); the message may quote the model's own keys and
    is never logged."""
    if not isinstance(value, dict):
        return [("malformed", "slots must be an object")]
    props: dict[str, Any] = schema.get("properties", {})
    out = [("unknown_slot", f"unknown slot {k!r}") for k in value if k not in props]
    out += [("missing_slot", f"missing slot {k!r}") for k in schema.get("required", []) if k not in value]
    for k, v in value.items():
        spec = props.get(k)
        if spec is None:
            continue
        if not any(_is(v, t) for t in _types(spec)):
            out.append(("wrong_type", f"slot {k!r} has the wrong type"))
            continue
        if v is None:
            continue
        if "enum" in spec and v not in spec["enum"]:
            out.append(("bad_value", f"slot {k!r} is not one of its values"))
        if isinstance(v, int | float) and not isinstance(v, bool) and (
                "minimum" in spec and v < spec["minimum"] or "maximum" in spec and v > spec["maximum"]):
            out.append(("out_of_range", f"slot {k!r} is out of range"))
        if isinstance(v, str):
            if "minLength" in spec and len(v) < spec["minLength"] or "maxLength" in spec and len(v) > spec["maxLength"]:
                out.append(("bad_value", f"slot {k!r} has the wrong length"))
            if "pattern" in spec and re.fullmatch(spec["pattern"], v) is None:
                out.append(("bad_value", f"slot {k!r} does not match its pattern"))
    return out


def problems(schema: dict[str, Any], value: Any) -> list[str]:
    """Why `value` does not satisfy `schema` (empty when it does)."""
    return [msg for _, msg in coded_problems(schema, value)]


def wire(spec: Any) -> Any:
    """A schema without the bounds structured-output modes refuse (minimum, maximum, lengths, patterns)."""
    if isinstance(spec, dict):
        return {k: ({n: wire(s) for n, s in v.items()} if k == "properties" and isinstance(v, dict) else wire(v))
                for k, v in spec.items() if k not in _BOUNDS}
    if isinstance(spec, list):
        return [wire(v) for v in spec]
    return spec
