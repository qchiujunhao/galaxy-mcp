"""Command-line options and the environment snapshot for the live suite.

Both are wired from the root tests/conftest.py: options added in a sub-directory conftest
are not seen when pytest runs from python/ without the path, and the environment has to
be read before any test module imports galaxy_mcp.server, whose import-time load_dotenv
would otherwise fill GALAXY_URL / GALAXY_API_KEY from a stray .env.
"""

from __future__ import annotations

import os
import re

import pytest

ENV_NAMES = (
    "GALAXY_URL",
    "GALAXY_API_KEY",
    "GALAXY_TEST_URL",
    "GALAXY_TEST_API_KEY",
    "GALAXY_LIVE_PYTHON_CMD",
    "GALAXY_LIVE_TS_CMD",
    "GALAXY_LIVE_ALLOW_PRODUCTION",
    "PATH",
    "HOME",
)
ENV_KEY = pytest.StashKey[dict[str, "str | None"]]()
WAIVABLE = ("network", "unprivileged-tools", "admin", "galaxy-version", "tools")


def add_live_options(parser: pytest.Parser) -> None:
    group = parser.getgroup("live", "live scenarios against a real Galaxy (opt in with -m live)")
    group.addoption(
        "--live-server",
        choices=("python", "typescript", "both"),
        default="both",
        help="which MCP server(s) to run the live scenarios against (default both)",
    )
    group.addoption(
        "--live-pack",
        action="append",
        default=[],
        metavar="PACK",
        help="run only this scenario pack (contract/scenarios/<PACK>.json); repeatable",
    )
    group.addoption(
        "--live-waive",
        action="append",
        default=[],
        choices=WAIVABLE,
        metavar="REQUIREMENT",
        help=f"skip, instead of failing, scenarios this Galaxy cannot run; one of {WAIVABLE}",
    )


def snapshot_live_env(config: pytest.Config) -> None:
    config.stash[ENV_KEY] = {name: os.environ.get(name) for name in ENV_NAMES}


def selected_servers(config: pytest.Config) -> list[str]:
    choice = config.getoption("--live-server")
    return ["python", "typescript"] if choice == "both" else [choice]


def deselect_unrequested_live(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep live tests out unless the -m expression names `live`.

    addopts' -m "not live" is replaced by any -m on the command line, so `-m "not slow"` on
    its own would otherwise run the live suite against whatever GALAXY_URL is exported.
    """
    if re.search(r"\blive\b", config.getoption("markexpr") or ""):
        return
    drop = [item for item in items if item.get_closest_marker("live")]
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = [item for item in items if not item.get_closest_marker("live")]
