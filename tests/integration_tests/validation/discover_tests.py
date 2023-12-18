from __future__ import annotations
import json
import sys
from collections.abc import Iterable
from typing import TypedDict

from .conformance_suite_config import ConformanceSuiteConfig
from .conformance_suite_configs import ALL_CONFORMANCE_SUITE_CONFIGS
from .conformance_suite_configurations.xbrl_2_1 import config as xbrl_2_1


LINUX = 'ubuntu-22.04'
MACOS = 'macos-12'
WINDOWS = 'windows-2022'
ALL_PYTHON_VERSIONS = (
    '3.8',
    '3.9',
    '3.10',
    '3.11',
)
LATEST_PYTHON_VERSION = '3.11'


class Entry(TypedDict, total=False):
    name: str
    cache: bool
    os: str
    python_version: str
    shard: str


def generate_config_entry(name: str, network_or_cache_required: bool, os: str, python_version: str, shard: str | None) -> Entry:
    e: Entry = {
        'name': name,
        'cache': network_or_cache_required,
        'os': os,
        'python_version': python_version,
    }
    if shard is not None:
        e['shard'] = shard
    return e


def generate_config_entries(config: ConformanceSuiteConfig, os: str, python_version: str) -> Iterable[Entry]:
    if config.shards == 1:
        yield generate_config_entry(
            name=config.name,
            network_or_cache_required=config.network_or_cache_required,
            os=os,
            python_version=python_version,
            shard=None,
        )
    else:
        for i in range(config.shards):
            yield generate_config_entry(
                name=config.name,
                network_or_cache_required=config.network_or_cache_required,
                os=os,
                python_version=python_version,
                shard=str(i),
            )


def main() -> None:
    output: list[Entry] = []
    config_names_seen: set[str] = set()
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
    json.dump(output, sys.stdout, indent=4)
    print()


if __name__ == '__main__':
    main()
