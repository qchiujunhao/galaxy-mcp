"""Offline checks on the live scenario packs and the registry's live section.

Part of the default unit run and needs no Galaxy: a scenario that names a parameter the
tool does not take, cites a row that does not exist, or references a binding nobody made
fails here, not on the nightly run.
"""

import pytest

from tests.live.loader import (
    EXPECTED_PACKS,
    check_ids,
    check_live_registry,
    check_ownership,
    check_pack_files,
    check_partition,
    check_ports,
    check_scenarios,
    check_schema_current,
    load_contract,
    missing_packs,
    pack_paths,
)


def _report(problems: list[str]) -> str:
    return "\n  " + "\n  ".join(problems)


@pytest.fixture(scope="module")
def contract():
    return load_contract()


def test_packs_load(contract):
    assert len(contract.packs) == len(pack_paths())


def test_pack_names_match_files(contract):
    problems = check_pack_files(contract)
    assert not problems, _report(problems)


def test_scenario_ids_unique(contract):
    problems = check_ids(contract)
    assert not problems, _report(problems)


def test_scenarios_are_well_formed(contract):
    problems, _ = check_scenarios(contract)
    assert not problems, _report(problems)


def test_pack_ownership(contract):
    problems = check_ownership(contract)
    assert not problems, _report(problems)


def test_live_registry_section(contract):
    _, cited = check_scenarios(contract)
    problems = check_live_registry(contract, cited)
    assert not problems, _report(problems)


def test_schema_is_current():
    problems = check_schema_current()
    assert not problems, _report(problems)


def _require_all_packs(contract):
    absent = missing_packs(contract)
    if absent:
        # Phase 2 of the plan: the packs land in parallel. Remove this once all four are in.
        pytest.skip(f"pending packs {absent} (of {list(EXPECTED_PACKS)})")


def test_packs_partition_the_manifest(contract):
    _require_all_packs(contract)
    problems = check_partition(contract)
    assert not problems, _report(problems)


def test_every_legacy_live_test_is_ported(contract):
    _require_all_packs(contract)
    problems = check_ports(contract)
    assert not problems, _report(problems)
