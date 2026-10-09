"""Purge what crashed live runs left on a test Galaxy.

Every run cleans up after itself, but a killed process cannot, and one thing no run can
register: when Galaxy refuses an invocation made without a history_id it has already
created "History from <workflow> workflow", and the failed call never says so. Everything
a run creates carries "mcp-live-" in its name or slug, so this deletes those that have not
been touched for --hours (default 6), which leaves concurrent runs alone.

    uv run python -m tests.live.sweep              # with GALAXY_URL / GALAXY_API_KEY set
    uv run python -m tests.live.sweep --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from bioblend.galaxy import GalaxyInstance

from .options import production_refusal

MARK = "mcp-live-"


def _ours(name: str | None) -> bool:
    name = name or ""
    return name.startswith(MARK) or name.startswith(f"History from {MARK}")


def _old(item: dict[str, Any], cutoff: datetime) -> bool:
    stamp = item.get("update_time") or item.get("create_time")
    if not stamp:
        return True
    when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when < cutoff


def sweep(gi: GalaxyInstance, hours: float, dry_run: bool) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    done: list[str] = []

    for h in gi.histories.get_histories(keys=["id", "name", "update_time"]):
        if _ours(h.get("name")) and _old(h, cutoff):
            done.append(f"history {h['id']} {h['name']}")
            if not dry_run:
                gi.histories.delete_history(h["id"], purge=True)

    for w in gi.workflows.get_workflows():
        if _ours(w.get("name")) and _old(w, cutoff):
            done.append(f"workflow {w['id']} {w['name']}")
            if not dry_run:
                gi.workflows.delete_workflow(w["id"])

    reply = gi.make_get_request(f"{gi.url}/pages", params={"search": MARK, "limit": 500})
    reply.raise_for_status()
    for p in reply.json():
        if (p.get("slug") or "").startswith(MARK) and _old(p, cutoff):
            done.append(f"page {p['id']} {p['slug']}")
            if not dry_run:
                gi.make_delete_request(f"{gi.url}/pages/{p['id']}")
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    url, key = os.environ.get("GALAXY_URL"), os.environ.get("GALAXY_API_KEY")
    if not url or not key:
        print("GALAXY_URL and GALAXY_API_KEY must be set", file=sys.stderr)
        return 2
    refusal = production_refusal(url.rstrip("/"), os.environ.get("GALAXY_LIVE_ALLOW_PRODUCTION"))
    if refusal:
        print(f"sweep: {refusal}", file=sys.stderr)
        return 2
    for line in sweep(GalaxyInstance(url, key=key), args.hours, args.dry_run):
        print(("would purge " if args.dry_run else "purged ") + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
