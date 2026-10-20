"""The assertion vocabulary scenarios use, evaluated against a view.

A view is plain JSON: the normalised tool result for a call step, Galaxy's own JSON for a
verify step. Paths are dotted, integers index lists, and "" is the view itself.
"""

from __future__ import annotations

import re
from typing import Any

from .model import Assertion, PathRef


class _Missing:
    def __repr__(self) -> str:
        return "<missing>"


MISSING: Any = _Missing()


def get_path(view: Any, path: str) -> Any:
    if path == "":
        return view
    node = view
    for part in path.split("."):
        if isinstance(node, dict):
            if part not in node:
                return MISSING
            node = node[part]
        elif isinstance(node, list):
            if not re.fullmatch(r"-?\d+", part):
                return MISSING
            index = int(part)
            if not -len(node) <= index < len(node):
                return MISSING
            node = node[index]
        else:
            return MISSING
    return node


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def json_equal(a: Any, b: Any) -> bool:
    """Deep equality with JSON's idea of numbers: 0 == 0.0, but True is not 1."""
    if is_number(a) and is_number(b):
        return bool(a == b)
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b, strict=True))
    return type(a) is type(b) and bool(a == b)


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if is_number(value):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _short(value: Any, limit: int = 300) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "..."


_COMPARE = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
}


def evaluate(view: Any, assertion: Assertion, prefix: str = "") -> list[str]:
    """Every way `assertion` fails on `view`; empty when it holds."""
    op = assertion.op
    shown = f"{prefix}{assertion.path or '<root>'}"
    actual = get_path(view, assertion.path)

    if op == "exists":
        present = actual is not MISSING
        if present != assertion.exists:
            return [f"{shown}: expected {'present' if assertion.exists else 'absent'}"]
        return []
    if actual is MISSING:
        return [f"{shown}: missing (asserting {op})"]

    def fail(why: str) -> list[str]:
        return [f"{shown}: {why}; actual {_short(actual)}"]

    if op == "equals":
        return (
            []
            if json_equal(actual, assertion.equals)
            else fail(f"expected {_short(assertion.equals)}")
        )
    if op == "not_equals":
        return (
            fail(f"expected anything but {_short(assertion.not_equals)}")
            if json_equal(actual, assertion.not_equals)
            else []
        )
    if op == "in_":
        assert assertion.in_ is not None
        return (
            []
            if any(json_equal(actual, v) for v in assertion.in_)
            else fail(f"expected one of {assertion.in_}")
        )
    if op == "type":
        kind = json_type(actual)
        if assertion.type == "integer":
            ok = is_number(actual) and float(actual).is_integer()
        else:
            ok = kind == assertion.type
        return [] if ok else fail(f"expected type {assertion.type}, got {kind}")
    if op in ("contains", "not_contains", "matches"):
        if not isinstance(actual, str):
            return fail(f"{op} needs a string")
        if op == "contains":
            assert assertion.contains is not None
            return (
                []
                if assertion.contains in actual
                else fail(f"expected to contain {assertion.contains!r}")
            )
        if op == "not_contains":
            assert assertion.not_contains is not None
            return (
                fail(f"expected not to contain {assertion.not_contains!r}")
                if assertion.not_contains in actual
                else []
            )
        assert assertion.matches is not None
        return (
            []
            if re.search(assertion.matches, actual)
            else fail(f"expected to match /{assertion.matches}/")
        )
    if op in ("keys_include", "keys_exclude", "keys_equal"):
        if not isinstance(actual, dict):
            return fail(f"{op} needs an object")
        keys = set(actual)
        want = set(getattr(assertion, op))
        if op == "keys_include" and not want <= keys:
            return [f"{shown}: missing keys {sorted(want - keys)}; has {sorted(keys)}"]
        if op == "keys_exclude" and want & keys:
            return [f"{shown}: unexpected keys {sorted(want & keys)}"]
        if op == "keys_equal" and want != keys:
            return [
                f"{shown}: keys differ: missing {sorted(want - keys)}, extra {sorted(keys - want)}"
            ]
        return []
    if op == "length":
        if not isinstance(actual, (list, str, dict)):
            return fail("length needs a list, string or object")
        assert assertion.length is not None
        n = len(actual)
        out = []
        for name in assertion.length.model_fields_set:
            bound = getattr(assertion.length, name)
            if not _COMPARE[name](n, bound):
                out.append(f"{shown}: length {n}, expected {name} {bound}")
        return out
    if op in ("gt", "gte", "lt", "lte"):
        bound = getattr(assertion, op)
        if isinstance(bound, PathRef):
            other = get_path(view, bound.path)
            if not is_number(other):
                return [f"{shown}: {op} against {bound.path}, which is {_short(other)}"]
            bound = other
        if not is_number(bound):
            return [f"{shown}: {op} needs a number to compare with, got {_short(bound)}"]
        if not is_number(actual):
            return fail(f"{op} needs a number")
        return [] if _COMPARE[op](actual, bound) else fail(f"expected {op} {bound}")
    if op == "has_item":
        if not isinstance(actual, list):
            return fail("has_item needs a list")
        partial = assertion.has_item or {}
        for item in actual:
            if isinstance(item, dict) and all(
                k in item and json_equal(item[k], v) for k, v in partial.items()
            ):
                return []
        return [f"{shown}: no element has {_short(partial)} ({len(actual)} elements)"]
    if op == "each":
        if not isinstance(actual, list):
            return fail("each needs a list")
        out = []
        for i, item in enumerate(actual):
            for sub in assertion.each or []:
                out += evaluate(item, sub, prefix=f"{shown}.{i}.")
        return out
    if op == "sorted":
        if not isinstance(actual, list):
            return fail("sorted needs a list")
        assert assertion.sorted is not None
        key = assertion.sorted.key
        values = [get_path(item, key) if key else item for item in actual]
        if any(v is MISSING for v in values):
            return [f"{shown}: some elements have no {key!r}"]
        try:
            ordered = sorted(values, reverse=assertion.sorted.order == "desc")
        except TypeError:
            return [f"{shown}: values of {key!r} are not comparable: {_short(values)}"]
        return (
            []
            if values == ordered
            else [f"{shown}: not sorted {assertion.sorted.order} by {key!r}: {_short(values)}"]
        )
    raise AssertionError(f"unhandled assertion op {op}")


def evaluate_all(view: Any, assertions: list[Assertion]) -> list[str]:
    out: list[str] = []
    for assertion in assertions:
        out += evaluate(view, assertion)
    return out
