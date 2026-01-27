from __future__ import annotations
import json
import sys
from collections.abc import Iterable
from typing import TypedDict

from .conformance_suite_config import ConformanceSuiteConfig
from .conformance_suite_configs import CI_CONFORMANCE_SUITE_CONFIGS
from .conformance_suite_configurations.efm_current import config as efm_current
from .conformance_suite_configurations.xbrl_2_1 import config as xbrl_2_1
from ..github import LINUX, MACOS, WINDOWS


ALL_PYTHON_VERSIONS = (
    '3.10',
    '3.11',
    '3.12',
    '3.13',
    '3.14.2',
)
LATEST_PYTHON_VERSION = '3.14.2'


class Entry(TypedDict, total=False):
    environment: str
    name: str
    short_name: str
    os: str
    python_version: str
    shard: str
    shard_count: str


def generate_config_entry(name: str, short_name: str, os: str, private: bool, python_version: str, shard: str | None, shard_count: int | None) -> Entry:
    e: Entry = {
        'environment': 'integration-tests' if private else 'none',
        'name': name,
        'short_name': short_name,
        'os': os,
        'python_version': python_version,
    }
    if shard is not None:
        e['shard'] = shard
    if shard_count is not None:
        e['shard_count'] = str(shard_count)
    return e


def generate_config_entries(config: ConformanceSuiteConfig, os: str, python_version: str, minimal: bool = False) -> Iterable[Entry]:
    if config.ci_config.shard_count == 1:
        yield generate_config_entry(
            name=config.name,
            short_name=config.name,
            os=os,
            private=config.has_private_asset,
            python_version=python_version,
            shard=None,
            shard_count=None,
        )
    else:
        shard_range = [0] if minimal else range(0, config.ci_config.shard_count, 1)
        for shard in shard_range:
            yield generate_config_entry(
                name=config.name,
                short_name=config.name,
                os=os,
                private=config.has_private_asset,
                python_version=python_version,
                shard=str(shard),
                shard_count=config.ci_config.shard_count,
            )


def main() -> None:
    output: list[Entry] = []
    config_names_seen: set[str] = set()
    private = False
    for config in CI_CONFORMANCE_SUITE_CONFIGS:
        if config.ci_config.fast:
            config_names_seen.add(config.name)
            private |= config.has_private_asset
    for os in [LINUX, MACOS, WINDOWS]:
        output.append(generate_config_entry(
            name=','.join(sorted(config_names_seen)),
            short_name='fast suites',
            os=os,
            private=private,
            python_version=LATEST_PYTHON_VERSION,
            shard=None,
            shard_count=None,
        ))

    for config in CI_CONFORMANCE_SUITE_CONFIGS:
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
