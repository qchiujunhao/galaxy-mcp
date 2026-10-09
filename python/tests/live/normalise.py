"""Turn a wire result into the view scenarios assert on, apply registry adapters, and
compare two servers' views for the parity test.

The same rules run for both servers. Anything that does not fit them is a HarnessError
(the scenario or the harness is wrong) or a FindingError (a server answered in a way no client
should have to cope with); neither is something a scenario can `expect`.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from mcp.types import CallToolResult

from .assertions import json_equal, json_type
from .model import CutFromOp, DropOp, ExpectFailureOp, LiveRow, RstripOp, SetOp, SubOp

ENVELOPE_KEYS = {"data", "success", "message", "count", "pagination"}
TOOL_PREFIX = "Error calling tool '{tool}': "
PY_ARGS = re.compile(r"^\d+ validation errors? for call\[(?P<tool>[^\]]+)\]")
TS_ARGS_PREFIX = "MCP error -32602: Input validation error:"


class HarnessError(Exception):
    """The scenario, the registry or the harness is wrong -- not a server."""


class FindingError(AssertionError):
    """A server answered in a way the normaliser refuses to paper over."""


def wire(result: CallToolResult) -> dict[str, Any]:
    return result.model_dump(by_alias=True, mode="json", exclude_none=True)


def to_view(tool: str, result: CallToolResult, server: str, argument_text: bool) -> dict[str, Any]:
    raw = wire(result)
    content = raw.get("content", [])
    if len(content) != 1 or content[0].get("type") != "text":
        raise FindingError(
            f"{server} {tool}: expected exactly one text content block, "
            f"got {json.dumps(content)[:500]}"
        )
    text = content[0]["text"]

    if raw.get("isError"):
        prefix = TOOL_PREFIX.format(tool=tool)
        if text.startswith(prefix):
            return {
                "outcome": "failure",
                "failure": {"kind": "tool", "sentence": text[len(prefix) :]},
            }
        py = PY_ARGS.match(text)
        if (py and py.group("tool") == tool) or text.startswith(TS_ARGS_PREFIX):
            if not argument_text:
                raise HarnessError(
                    f"{server} {tool}: argument-validation text, but "
                    f"live.normalization.argumentValidationText is disabled: {text[:300]!r}"
                )
            return {"outcome": "failure", "failure": {"kind": "arguments", "sentence": text}}
        raise HarnessError(f"{server} {tool}: unrecognised error text: {text[:500]!r}")

    try:
        envelope = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FindingError(
            f"{server} {tool}: success text is not JSON ({exc}): {text[:300]!r}"
        ) from exc
    structured = raw.get("structuredContent")
    if structured is not None and not json_equal(structured, envelope):
        raise FindingError(
            f"{server} {tool}: structuredContent and content[0].text disagree, so text-only "
            "clients read a different answer"
        )
    if not isinstance(envelope, dict) or set(envelope) != ENVELOPE_KEYS:
        keys = sorted(envelope) if isinstance(envelope, dict) else type(envelope).__name__
        raise FindingError(
            f"{server} {tool}: envelope keys {keys}, expected {sorted(ENVELOPE_KEYS)}"
        )
    if envelope["success"] is not True:
        raise FindingError(
            f"{server} {tool}: a success result says success={envelope['success']!r}"
        )
    return {"outcome": "success", **envelope}


# --- adapters ----------------------------------------------------------------------------


def _locate(node: Any, parts: list[str]) -> list[tuple[Any, str | int]]:
    """(container, key) for every place `parts` names; `*` matches each list element."""
    if not parts:
        return []
    head, rest = parts[0], parts[1:]
    if head == "*":
        if not isinstance(node, list):
            return []
        keys: list[str | int] = list(range(len(node)))
    elif isinstance(node, dict):
        keys = [head] if head in node else []
    elif isinstance(node, list) and re.fullmatch(r"\d+", head) and int(head) < len(node):
        keys = [int(head)]
    else:
        return []
    out: list[tuple[Any, str | int]] = []
    for key in keys:
        if rest:
            out += _locate(node[key], rest)  # type: ignore[index]
        else:
            out.append((node, key))
    return out


def _places(view: Any, path: str) -> list[tuple[Any, str | int]]:
    return _locate(view, path.split(".")) if path else []


def _rewrite_strings(view: Any, path: str, fn: Any) -> None:
    for container, key in _places(view, path):
        value = container[key]
        if isinstance(value, str):
            container[key] = fn(value)


def apply_ops(view: dict[str, Any], row: LiveRow) -> dict[str, Any]:
    out = copy.deepcopy(view)
    for op in row.ops:
        if isinstance(op, DropOp):
            for path in op.drop:
                # Delete from the end so list indexes stay valid.
                for container, key in reversed(_places(out, path)):
                    del container[key]
        elif isinstance(op, RstripOp):
            chars = op.rstrip.chars
            for path in op.rstrip.paths:
                _rewrite_strings(out, path, lambda s, c=chars: s.rstrip(c))
        elif isinstance(op, SubOp):
            for spec in op.sub:
                _rewrite_strings(
                    out, spec.path, lambda s, p=spec.pattern, r=spec.replace: re.sub(p, r, s)
                )
        elif isinstance(op, CutFromOp):
            marker = op.cut_from.marker
            _rewrite_strings(
                out, op.cut_from.path, lambda s, m=marker: s.split(m, 1)[0] if m in s else s
            )
        elif isinstance(op, SetOp):
            for path, value in op.set.items():
                for container, key in _places(out, path):
                    container[key] = copy.deepcopy(value)
        elif isinstance(op, ExpectFailureOp):
            raise HarnessError(f"{row.key}: expect failure is not a rewrite")
    return out


# --- parity ------------------------------------------------------------------------------

TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
GALAXY_ID = re.compile(r"(?<![0-9a-f])[0-9a-f]{16}(?![0-9a-f])")


def mask_string(text: str, replacements: list[tuple[str, str]]) -> str:
    for value, token in replacements:
        text = text.replace(value, token)
    text = TIMESTAMP.sub("<time>", text)
    text = UUID.sub("<uuid>", text)
    return GALAXY_ID.sub("<id>", text)


def mask_value(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        return mask_string(value, replacements)
    if isinstance(value, list):
        return [mask_value(v, replacements) for v in value]
    if isinstance(value, dict):
        # Keys too: Galaxy keys some maps by id, and those must not read as a shape change.
        return {mask_string(k, replacements): mask_value(v, replacements) for k, v in value.items()}
    return value


def apply_step_masks(view: Any, masks: list[tuple[str, str]]) -> tuple[Any, list[int]]:
    """Replace each mask's matches with <masked>; how many places each one touched."""
    out = copy.deepcopy(view)
    hits = []
    for path, pattern in masks:
        count = 0

        def sub(s: str, p: str = pattern) -> str:
            nonlocal count
            new, n = re.subn(p, "<masked>", s)
            count += n
            return new

        _rewrite_strings(out, path, sub)
        hits.append(count)
    return out, hits


# A shape is None (null: matches anything), a frozenset of scalar type names,
# ("object", {key: shape}) or ("list", shape-of-elements or None when empty).
Shape = Any


def shape_of(value: Any) -> Shape:
    if value is None:
        return None
    if isinstance(value, dict):
        return ("object", {k: shape_of(v) for k, v in value.items()})
    if isinstance(value, list):
        merged: Shape = None
        for item in value:
            merged = merge_shapes(merged, shape_of(item))
        return ("list", merged)
    return frozenset({json_type(value)})


def merge_shapes(a: Shape, b: Shape) -> Shape:
    if a is None:
        return b
    if b is None:
        return a
    if isinstance(a, frozenset) and isinstance(b, frozenset):
        return a | b
    if isinstance(a, tuple) and isinstance(b, tuple) and a[0] == b[0]:
        if a[0] == "list":
            return ("list", merge_shapes(a[1], b[1]))
        keys = set(a[1]) | set(b[1])
        return ("object", {k: merge_shapes(a[1].get(k), b[1].get(k)) for k in keys})
    return frozenset({_describe(a), _describe(b)})


def _describe(shape: Shape) -> str:
    if shape is None:
        return "null"
    if isinstance(shape, frozenset):
        return "|".join(sorted(shape))
    return str(shape[0])


def shape_diff(a: Shape, b: Shape, path: str = "") -> list[str]:
    where = path or "<root>"
    if a is None or b is None:
        return []
    if isinstance(a, tuple) and isinstance(b, tuple) and a[0] == b[0]:
        if a[0] == "list":
            return shape_diff(a[1], b[1], f"{path}[]")
        out = []
        only_a, only_b = sorted(set(a[1]) - set(b[1])), sorted(set(b[1]) - set(a[1]))
        if only_a or only_b:
            out.append(f"{where}: keys only on python {only_a}, only on typescript {only_b}")
        for key in sorted(set(a[1]) & set(b[1])):
            out += shape_diff(a[1][key], b[1][key], f"{path}.{key}" if path else key)
        return out
    if a != b:
        return [f"{where}: python {_describe(a)}, typescript {_describe(b)}"]
    return []


TOKEN = re.compile(r"(<[^<>]+>)")


def _weak_equal(a: str, b: str, weak: frozenset[str]) -> bool:
    if a == b:
        return True
    pa, pb = TOKEN.split(a), TOKEN.split(b)
    if len(pa) != len(pb):
        return False
    return all(
        x == y or (x in weak and y == "<id>") or (y in weak and x == "<id>")
        for x, y in zip(pa, pb, strict=True)
    )


def exact_diff(a: Any, b: Any, path: str = "", weak: frozenset[str] = frozenset()) -> list[str]:
    """Deep differences; `weak` binding tokens count as equal to a plain <id>.

    Galaxy encodes ids per table with one key, so an id from another table (a contents
    item's dataset_id) can spell the same as a bound HDA id on one server and not on the
    other. Comparing those tokens as <id> keeps the check from failing at random, and two
    different binding tokens still differ.
    """
    where = path or "<root>"
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
        if only_a or only_b:
            out.append(f"{where}: keys only on python {only_a}, only on typescript {only_b}")
        for key in sorted(set(a) & set(b)):
            out += exact_diff(a[key], b[key], f"{path}.{key}" if path else key, weak)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{where}: python has {len(a)} elements, typescript {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out += exact_diff(x, y, f"{path}.{i}" if path else str(i), weak)
        return out
    if json_equal(a, b):
        return []
    if isinstance(a, str) and isinstance(b, str) and _weak_equal(a, b, weak):
        return []
    return [f"{where}: python {json.dumps(a)[:200]}, typescript {json.dumps(b)[:200]}"]


def compare_views(
    py: dict[str, Any], ts: dict[str, Any], mode: str, weak: frozenset[str] = frozenset()
) -> list[str]:
    if py.get("outcome") != ts.get("outcome"):
        return [
            f"outcome: python {py.get('outcome')}, typescript {ts.get('outcome')} "
            f"({_failure_hint(py)} / {_failure_hint(ts)})"
        ]
    if py["outcome"] == "failure":
        pk, tk = py["failure"]["kind"], ts["failure"]["kind"]
        if pk != tk:
            return [f"failure.kind: python {pk}, typescript {tk}"]
        if pk == "arguments":
            return []
        ps, tsent = py["failure"]["sentence"], ts["failure"]["sentence"]
        if _weak_equal(ps, tsent, weak):
            return []
        return [f"failure.sentence:\n  python:     {ps}\n  typescript: {tsent}"]
    if mode == "exact":
        return exact_diff(py, ts, weak=weak)
    return shape_diff(shape_of(py), shape_of(ts))


def _failure_hint(view: dict[str, Any]) -> str:
    if view.get("outcome") == "failure":
        return str(view["failure"]["sentence"])[:200]
    return str(view.get("message"))[:200]
