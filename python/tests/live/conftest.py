"""Session plumbing for the live suite: parametrisation, preflight, server subprocesses.

Nothing here skips because Galaxy is missing. The live tests are deselected by default
(`-m "not live"` in addopts); once one is selected, the preflight either finds a usable
Galaxy and a current build or stops the whole run, saying which.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from bioblend.galaxy import GalaxyInstance

from .loader import Contract, check_scenarios, load_contract
from .model import Pack, Scenario
from .options import ENV_KEY, production_refusal, selected_servers
from .runner import LiveContext
from .servers import ServerPool, launch_spec, ts_build_problem

EXIT_CODE = 4


class _ContractBroken:
    """Stands in for the parameters when the contract will not load, so the error surfaces
    as a failing live test (and in the offline check) rather than a collection error in
    the default unit run."""

    def __init__(self, error: Exception) -> None:
        self.error = error


def _selected_packs(config: pytest.Config, contract: Contract) -> list[Pack]:
    wanted = config.getoption("--live-pack")
    packs = [p for p in contract.packs if not wanted or p.pack in wanted]
    unknown = set(wanted) - {p.pack for p in contract.packs}
    if unknown:
        raise ValueError(f"--live-pack {sorted(unknown)}: no such pack under contract/scenarios")
    return packs


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    config = metafunc.config
    servers = selected_servers(config)
    try:
        contract = load_contract()
        packs = _selected_packs(config, contract)
    except Exception as exc:
        for name in ("live_server_name", "live_case", "live_parity_case"):
            if name in metafunc.fixturenames:
                metafunc.parametrize(name, [_ContractBroken(exc)], ids=["contract-error"])
        return

    if "live_server_name" in metafunc.fixturenames:
        metafunc.parametrize("live_server_name", servers)
    if "live_case" in metafunc.fixturenames:
        cases = [
            (pack, scenario, server)
            for pack in packs
            for scenario in pack.scenarios
            for server in servers
            if server in scenario.servers
        ]
        metafunc.parametrize("live_case", cases, ids=[f"{c[2]}-{c[1].id}" for c in cases])
    if "live_parity_case" in metafunc.fixturenames:
        both = [
            (pack, scenario)
            for pack in packs
            for scenario in pack.scenarios
            if len(servers) == 2 and len(scenario.servers) == 2
        ]
        metafunc.parametrize("live_parity_case", both, ids=[c[1].id for c in both])


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # One server means nothing to compare: deselect, so it never reads as a skip.
    if len(selected_servers(config)) == 2:
        return
    keep: list[pytest.Item] = []
    drop: list[pytest.Item] = []
    for item in items:
        (drop if item.name.startswith("test_parity") else keep).append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep


def _exit(message: str) -> None:
    pytest.exit(f"live preflight: {message}", returncode=EXIT_CODE)


def _scenarios_for(config: pytest.Config, contract: Contract) -> list[Scenario]:
    return [s for p in _selected_packs(config, contract) for s in p.scenarios]


@pytest.fixture(scope="session")
def live_ctx(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> LiveContext:
    config = request.config
    env = config.stash[ENV_KEY]

    old = [n for n in ("GALAXY_TEST_URL", "GALAXY_TEST_API_KEY") if env.get(n)]
    if old:
        _exit(
            f"{', '.join(old)} renamed to GALAXY_URL / GALAXY_API_KEY in #119; unset the old "
            "name(s) and export the new ones"
        )
    url, key = env.get("GALAXY_URL"), env.get("GALAXY_API_KEY")
    if not url or not key:
        missing = [n for n, v in (("GALAXY_URL", url), ("GALAXY_API_KEY", key)) if not v]
        _exit(f"{' and '.join(missing)} not set; the live suite needs a Galaxy to run against")
    assert url is not None
    assert key is not None
    # Handed to both servers without a trailing slash, so a difference in how a server
    # spells it back is the server's, not an accident of how someone exported the variable.
    url = url.rstrip("/")
    refusal = production_refusal(url, env.get("GALAXY_LIVE_ALLOW_PRODUCTION"))
    if refusal:
        _exit(refusal)

    api = url.rstrip("/") + "/api"
    try:
        version_reply = requests.get(f"{api}/version", timeout=15)
        version_reply.raise_for_status()
        user_reply = requests.get(f"{api}/users/current", headers={"x-api-key": key}, timeout=15)
    except requests.RequestException as exc:
        _exit(f"cannot reach Galaxy at {url}: {exc}")
    if user_reply.status_code != 200 or not user_reply.json().get("id"):
        _exit(
            f"Galaxy at {url} rejected GALAXY_API_KEY ({user_reply.status_code}): "
            f"{user_reply.text[:300]}"
        )
    version_json = version_reply.json()
    version = ".".join(
        p for p in (version_json.get("version_major"), version_json.get("version_minor")) if p
    )
    user = user_reply.json()

    servers = selected_servers(config)
    if "typescript" in servers and not launch_spec("typescript", env).overridden:
        problem = ts_build_problem()
        if problem:
            _exit(f"{problem}; run `pnpm install && pnpm -r build` in typescript/")

    try:
        contract = load_contract()
        scenarios = _scenarios_for(config, contract)
    except Exception as exc:
        _exit(f"the scenario contract does not load: {exc}")
    # Only the selected packs: one pack's unfinished citation must not stop another's run.
    # The offline check covers the whole contract.
    problems, _ = check_scenarios(contract, _selected_packs(config, contract))
    if problems:
        _exit(
            "the scenario files have problems (see tests/test_live_scenario_files.py):\n  "
            + "\n  ".join(problems)
        )

    log_dir = Path(tempfile.mkdtemp(prefix="mcp-live-logs-"))
    ctx = LiveContext(
        gi=GalaxyInstance(url, key=key),
        galaxy_url=url,
        api_key=key,
        version=version,
        user=user,
        contract=contract,
        waivers=set(config.getoption("--live-waive")),
        log_dir=log_dir,
    )

    needed_tools = sorted({t for s in scenarios for t in s.requires.tools})
    absent = [t for t in needed_tools if not ctx.has_tool(t)]
    caps = ctx.capabilities
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    lines = [
        f"live Galaxy: {url} (Galaxy {version}) as {user.get('email')}",
        f"servers: {', '.join(' '.join(launch_spec(s, env).command) for s in servers)}",
        f"capabilities: {', '.join(f'{k}={v}' for k, v in caps.items())}",
        f"Galaxy tools missing: {absent or 'none'}; waivers: {sorted(ctx.waivers) or 'none'}",
        f"server stderr logs: {log_dir}",
    ]
    if reporter is not None:
        reporter.write_line("")
        for line in lines:
            reporter.write_line(line)
    return ctx


@pytest.fixture(scope="session")
def live_servers(live_ctx: LiveContext, request: pytest.FixtureRequest) -> Iterator[ServerPool]:
    env = request.config.stash[ENV_KEY]
    pool = ServerPool(
        env,
        live_ctx.galaxy_url,
        live_ctx.api_key,
        env.get("PATH") or "/usr/bin:/bin",
        env.get("HOME") or tempfile.gettempdir(),
        live_ctx.log_dir,
    )
    yield pool
    pool.close()
