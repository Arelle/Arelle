from __future__ import annotations
import json
import sys
from collections.abc import Iterable
from typing import TypedDict

from .conformance_suite_config import ConformanceSuiteConfig
from .conformance_suite_configs import ALL_CONFORMANCE_SUITE_CONFIGS


class Entry(TypedDict, total=False):
    name: str
    cache: bool
    shard: str


def generate_config_entry(name: str, network_or_cache_required: bool, shard: str | None) -> Entry:
    e: Entry = {
        'name': name,
        'cache': network_or_cache_required,
    }
    if shard is not None:
        e['shard'] = shard
    return e


def generate_config_entries(config: ConformanceSuiteConfig) -> Iterable[Entry]:
    if config.shards == 1:
        yield generate_config_entry(
            name=config.name,
            network_or_cache_required=config.network_or_cache_required,
            shard=None,
        )
    else:
        for i in range(config.shards):
            yield generate_config_entry(
                name=config.name,
                network_or_cache_required=config.network_or_cache_required,
                shard=str(i),
            )


def main() -> None:
    output: list[Entry] = []
    for config in ALL_CONFORMANCE_SUITE_CONFIGS:
        output.extend(generate_config_entries(config))
    json.dump(output, sys.stdout, indent=4)
    print()


if __name__ == '__main__':
    main()
