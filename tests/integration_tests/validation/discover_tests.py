from __future__ import annotations
import json
import sys
from collections.abc import Iterable
from typing import TypedDict

from .conformance_suite_config import ConformanceSuiteConfig
from .conformance_suite_configs import ALL_CONFORMANCE_SUITE_CONFIGS
from .conformance_suite_configurations.efm_current import config as efm_current
from .conformance_suite_configurations.xbrl_2_1 import config as xbrl_2_1


LINUX = 'ubuntu-22.04'
MACOS = 'macos-12'
WINDOWS = 'windows-2022'
ALL_PYTHON_VERSIONS = (
    '3.8',
    '3.9',
    '3.10',
    '3.11',
    '3.12',
)
LATEST_PYTHON_VERSION = '3.12'
# number of cores on the runners
# https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners/about-github-hosted-runners#supported-runners-and-hardware-resources
OS_CORES = {
    LINUX: 4,
    MACOS: 3,
    WINDOWS: 4,
}
FAST_CONFIG_NAMES = {
    'esef_xhtml_2021',
    'esef_xhtml_2022',
    'esef_xhtml_2023',
    'xbrl_calculations_1_1',
    'xbrl_dimensions_1_0',
    'xbrl_dtr_2024_01_31',
    'xbrl_extensible_enumerations_1_0',
    'xbrl_extensible_enumerations_2_0',
    'xbrl_formula_1_0_assertion_severity_2_0',
    'xbrl_formula_1_0_function_registry',
    'xbrl_link_role_registry_1_0',
    'xbrl_oim_1_0',
    'xbrl_taxonomy_packages_1_0',
    'xbrl_transformation_registry_3',
    'xbrl_utr_malformed_1_0',
    'xbrl_utr_registry_1_0',
    'xbrl_utr_structure_1_0',
}


class Entry(TypedDict, total=False):
    name: str
    short_name: str
    os: str
    python_version: str
    shard: str


def generate_config_entry(name: str, short_name: str, os: str, python_version: str, shard: str | None) -> Entry:
    e: Entry = {
        'name': name,
        'short_name': short_name,
        'os': os,
        'python_version': python_version,
    }
    if shard is not None:
        e['shard'] = shard
    return e


def generate_config_entries(config: ConformanceSuiteConfig, os: str, python_version: str, minimal: bool = False) -> Iterable[Entry]:
    if config.shards == 1:
        yield generate_config_entry(
            name=config.name,
            short_name=config.name,
            os=os,
            python_version=python_version,
            shard=None,
        )
    else:
        ncores = OS_CORES[os]
        shard_range = [0] if minimal else range(0, config.shards, ncores)
        for start in shard_range:
            end = min(config.shards, start + ncores) - 1
            yield generate_config_entry(
                name=config.name,
                short_name=config.name,
                os=os,
                python_version=python_version,
                shard=f'{start}-{end}',
            )


def main() -> None:
    output: list[Entry] = []
    config_names_seen: set[str] = set()
    for config in ALL_CONFORMANCE_SUITE_CONFIGS:
        if config.name in FAST_CONFIG_NAMES:
            assert not config.network_or_cache_required
            assert config.shards == 1
            config_names_seen.add(config.name)
    assert not (FAST_CONFIG_NAMES - config_names_seen), \
        f'Missing some fast configurations: {sorted(FAST_CONFIG_NAMES - config_names_seen)}'
    for os in [LINUX, MACOS, WINDOWS]:
        output.append(generate_config_entry(
            name=','.join(sorted(FAST_CONFIG_NAMES)),
            short_name='miscellaneous suites',
            os=os,
            python_version=LATEST_PYTHON_VERSION,
            shard=None,
        ))

    for config in ALL_CONFORMANCE_SUITE_CONFIGS:
        # configurations don't necessarily have unique names, e.g. malformed UTR
        if config.name in config_names_seen:
            continue
        config_names_seen.add(config.name)
        output.extend(generate_config_entries(config, os=LINUX, python_version=LATEST_PYTHON_VERSION))
    for os in [LINUX, MACOS, WINDOWS]:
        for python_version in ALL_PYTHON_VERSIONS:
            if os == LINUX and python_version == LATEST_PYTHON_VERSION:
                continue
            output.extend(generate_config_entries(xbrl_2_1, os=os, python_version=python_version))
    for os in [MACOS, WINDOWS]:
        output.extend(generate_config_entries(efm_current, os=os, python_version=LATEST_PYTHON_VERSION, minimal=True))

    json.dump(output, sys.stdout, indent=4)
    print()


if __name__ == '__main__':
    main()
