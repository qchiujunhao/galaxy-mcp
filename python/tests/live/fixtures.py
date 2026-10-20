"""Fixtures, waits, verifies and cleanup, all through a bookkeeping bioblend client.

None of this goes through the server under test: a fixture that used the tools it is
setting up for would hide the bugs the scenario is there to find. The client is plain
bioblend, not galaxy_mcp.client, for the same reason.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bioblend.galaxy import GalaxyInstance

from .loader import DATA
from .model import (
    CollectionElement,
    CollectionFixture,
    DatasetFixture,
    Fixture,
    HistoryFixture,
    InvocationFixture,
    LocalFileFixture,
    PageFixture,
    TempPathFixture,
    UserToolFixture,
    WaitSpec,
    WorkflowFixture,
)

TERMINAL = {
    "dataset": {"ok", "error", "failed_metadata", "discarded", "deferred", "paused", "deleted"},
    "job": {"ok", "error", "failed", "deleted", "deleting", "skipped", "stopped"},
    "invocation": {"scheduled", "cancelled", "failed", "completed"},
}
# Recent Galaxy moves an invocation on from scheduled to completed once its jobs finish,
# so a wait for scheduled is met by completed too rather than failing on the race.
LATER = {"invocation": {"scheduled": {"completed"}}}
POLL = 1.5


class WaitTimeoutError(AssertionError):
    pass


@dataclass
class Ledger:
    """Everything a run created, cleaned up newest first whatever happened."""

    gi: GalaxyInstance
    entries: list[tuple[str, str]] = field(default_factory=list)

    def add(self, kind: str, ident: str) -> None:
        if not isinstance(ident, str) or not ident:
            raise AssertionError(f"cannot register {kind} {ident!r} for cleanup")
        if (kind, ident) not in self.entries:
            self.entries.append((kind, ident))

    def cleanup(self) -> list[str]:
        errors = []
        for kind, ident in reversed(self.entries):
            try:
                CLEANERS[kind](self.gi, ident)
            except Exception as exc:
                errors.append(f"cleanup {kind} {ident}: {exc}")
        self.entries.clear()
        return errors


def _purge_history(gi: GalaxyInstance, ident: str) -> None:
    gi.histories.delete_history(ident, purge=True)


def _delete_workflow(gi: GalaxyInstance, ident: str) -> None:
    gi.workflows.delete_workflow(ident)


def _cancel_invocation(gi: GalaxyInstance, ident: str) -> None:
    state = gi.invocations.show_invocation(ident).get("state")
    if state not in TERMINAL["invocation"] - {"scheduled"}:
        gi.invocations.cancel_invocation(ident)


def _delete_page(gi: GalaxyInstance, ident: str) -> None:
    response = gi.make_delete_request(f"{gi.url}/pages/{ident}")
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()


def _deactivate_user_tool(gi: GalaxyInstance, ident: str) -> None:
    response = gi.make_delete_request(f"{gi.url}/unprivileged_tools/{ident}")
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()


CLEANERS: dict[str, Callable[[GalaxyInstance, str], None]] = {
    "history": _purge_history,
    "workflow": _delete_workflow,
    "invocation": _cancel_invocation,
    "page": _delete_page,
    "user_tool": _deactivate_user_tool,
}


def _post(gi: GalaxyInstance, route: str, payload: dict[str, Any]) -> Any:
    return gi.make_post_request(f"{gi.url}/{route}", payload=payload)


def _wait_jobs(gi: GalaxyInstance, job_ids: list[str], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    for job_id in job_ids:
        while True:
            state = gi.jobs.show_job(job_id)["state"]
            if state == "ok":
                break
            if state in TERMINAL["job"]:
                raise AssertionError(f"fixture job {job_id} ended {state}")
            if time.monotonic() > deadline:
                raise WaitTimeoutError(
                    f"fixture job {job_id} still {state} after {timeout:.0f}s -- Galaxy is "
                    "backed up or wedged"
                )
            time.sleep(POLL)


def _fetch_element(el: CollectionElement) -> dict[str, Any]:
    if el.elements is not None:
        return {"name": el.name, "elements": [_fetch_element(e) for e in el.elements]}
    return {"name": el.name, "src": "pasted", "paste_content": el.content, "ext": el.ext}


@dataclass
class FixtureContext:
    gi: GalaxyInstance
    ledger: Ledger
    tag: str
    tmp: Path
    pack: str
    timeout: float


def make_fixture(ctx: FixtureContext, fixture: Fixture, spec: Any) -> dict[str, Any]:
    """Create one fixture from its resolved spec; what it binds."""
    gi = ctx.gi
    name = f"{ctx.tag}-{fixture.as_}"
    if isinstance(spec, HistoryFixture):
        history = gi.histories.create_history(spec.name or name)
        ctx.ledger.add("history", history["id"])
        return {"id": history["id"], "name": history["name"]}
    if isinstance(spec, DatasetFixture):
        reply = _post(
            gi,
            "tools/fetch",
            {
                "history_id": spec.history,
                "targets": [
                    {
                        "destination": {"type": "hdas"},
                        "elements": [
                            {
                                "src": "pasted",
                                "paste_content": spec.content,
                                "ext": spec.ext,
                                "name": spec.name or fixture.as_,
                            }
                        ],
                    }
                ],
            },
        )
        _wait_jobs(gi, [j["id"] for j in reply["jobs"]], ctx.timeout)
        out = reply["outputs"][0]
        shown = gi.datasets.show_dataset(out["id"])
        return {
            "id": shown["id"],
            "name": shown["name"],
            "hid": shown["hid"],
            "history_id": spec.history,
        }
    if isinstance(spec, CollectionFixture):
        reply = _post(
            gi,
            "tools/fetch",
            {
                "history_id": spec.history,
                "targets": [
                    {
                        "destination": {"type": "hdca"},
                        "collection_type": spec.type,
                        "name": spec.name or fixture.as_,
                        "elements": [_fetch_element(e) for e in spec.elements],
                    }
                ],
            },
        )
        _wait_jobs(gi, [j["id"] for j in reply["jobs"]], ctx.timeout)
        hdca = gi.histories.show_dataset_collection(
            spec.history, reply["output_collections"][0]["id"]
        )
        return {
            "id": hdca["id"],
            "name": hdca["name"],
            "hid": hdca["hid"],
            "element_count": hdca["element_count"],
        }
    if isinstance(spec, WorkflowFixture):
        source = json.loads((DATA / ctx.pack / spec.file).read_text())
        source["name"] = f"{ctx.tag}-{source.get('name') or fixture.as_}"
        workflow = gi.workflows.import_workflow_dict(source)
        ctx.ledger.add("workflow", workflow["id"])
        return {"id": workflow["id"], "name": workflow["name"]}
    if isinstance(spec, InvocationFixture):
        invocation = gi.workflows.invoke_workflow(
            spec.workflow,
            inputs=spec.inputs,
            history_id=spec.history,
            inputs_by=spec.inputs_by,  # type: ignore[arg-type]
        )
        ctx.ledger.add("invocation", invocation["id"])
        return {"id": invocation["id"]}
    if isinstance(spec, PageFixture):
        payload: dict[str, Any] = {
            "title": spec.title or name,
            "slug": name.lower(),
            "content": spec.content,
            "content_format": "markdown",
        }
        if spec.history:
            payload["history_id"] = spec.history
        page = _post(gi, "pages", payload)
        ctx.ledger.add("page", page["id"])
        return {"id": page["id"], "slug": page["slug"], "title": page["title"]}
    if isinstance(spec, UserToolFixture):
        tool = _post(
            gi,
            "unprivileged_tools",
            {"src": "representation", "representation": spec.representation},
        )
        ctx.ledger.add("user_tool", tool["uuid"])
        return {"uuid": tool["uuid"], "id": tool.get("id") or tool["uuid"]}
    if isinstance(spec, LocalFileFixture):
        path = ctx.tmp / spec.name
        path.write_text(spec.content)
        return {
            "path": str(path),
            "name": spec.name,
            "content": spec.content,
            "size": path.stat().st_size,
        }
    if isinstance(spec, TempPathFixture):
        return {"path": str(ctx.tmp / spec.name)}
    raise AssertionError(f"no fixture kind for {type(spec).__name__}")


# --- waits -------------------------------------------------------------------------------


def _state(gi: GalaxyInstance, kind: str, ident: str) -> str:
    if kind == "dataset":
        return str(gi.datasets.show_dataset(ident)["state"])
    if kind == "job":
        return str(gi.jobs.show_job(ident)["state"])
    return str(gi.invocations.show_invocation(ident)["state"])


def wait_for(gi: GalaxyInstance, spec: WaitSpec, ident: str, deadline: float) -> str:
    kind = spec.kind
    if spec.state == "terminal":
        wanted = TERMINAL[kind]
    else:
        wanted = {spec.state} if isinstance(spec.state, str) else set(spec.state)
        later = LATER.get(kind, {})
        wanted |= {s for w in list(wanted) for s in later.get(w, set())}
    stop = min(time.monotonic() + spec.timeout, deadline)
    while True:
        state = _state(gi, kind, ident)
        if state in wanted:
            return state
        if state in TERMINAL[kind]:
            raise AssertionError(f"{kind} {ident} ended {state}, waiting for {sorted(wanted)}")
        if time.monotonic() > stop:
            raise WaitTimeoutError(
                f"{kind} {ident} still {state} after {spec.timeout:.0f}s, waiting for "
                f"{sorted(wanted)} -- Galaxy is backed up or wedged, not a tool failure"
            )
        time.sleep(POLL)


# --- verifies ----------------------------------------------------------------------------


def verify_view(gi: GalaxyInstance, kind: str, target: str) -> Any:
    if kind == "history":
        return gi.histories.show_history(target)
    if kind == "dataset":
        return gi.datasets.show_dataset(target)
    if kind == "dataset_text":
        raw = gi.datasets.download_dataset(target, require_ok_state=False)
        data = raw if isinstance(raw, bytes) else bytes(raw)
        return {"content": data.decode("utf-8", errors="replace"), "size": len(data)}
    if kind == "workflow":
        return gi.workflows.show_workflow(target)
    if kind == "invocation":
        return gi.invocations.show_invocation(target)
    if kind == "page":
        response = gi.make_get_request(f"{gi.url}/pages/{target}")
        response.raise_for_status()
        return response.json()
    if kind == "file":
        path = Path(target)
        if not path.is_file():
            return {"exists": False, "content": None, "size": None}
        data = path.read_bytes()
        return {
            "exists": True,
            "content": data.decode("utf-8", errors="replace"),
            "size": len(data),
        }
    raise AssertionError(f"no verify kind {kind}")
