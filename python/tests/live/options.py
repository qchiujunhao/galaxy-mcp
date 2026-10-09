"""Command-line options and the environment snapshot for the live suite.

Both are wired from the root tests/conftest.py: options added in a sub-directory conftest
are not seen when pytest runs from python/ without the path, and the environment has to
be read before any test module imports galaxy_mcp.server, whose import-time load_dotenv
would otherwise fill GALAXY_URL / GALAXY_API_KEY from a stray .env.
"""

from __future__ import annotations

import os

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
