from __future__ import annotations
import json
import sys
from typing import TypedDict

from .conformance_suite_configs import ALL_CONFORMANCE_SUITE_CONFIGS


class Entry(TypedDict, total=False):
    name: str
    cache: bool
    shard: str


output: list[Entry] = []
for config in ALL_CONFORMANCE_SUITE_CONFIGS:
    if config.shards == 1:
        output.append({
            'name': config.name,
            'cache': config.network_or_cache_required,
        })
    else:
        for i in range(config.shards):
            output.append({
                'name': config.name,
                'cache': config.network_or_cache_required,
                'shard': str(i),
            })
json.dump(output, sys.stdout, indent=4)
print()
