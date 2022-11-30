from __future__ import annotations
import json
import sys
from typing import TypedDict

from .conformance_suite_configs import ALL_CONFORMANCE_SUITE_CONFIGS


class Entry(TypedDict, total=False):
    name: str
    shard: str


output: list[Entry] = []
for config in ALL_CONFORMANCE_SUITE_CONFIGS:
    if config.shards == 1:
        output.append({'name': config.name})
    else:
        for i in range(config.shards):
            output.append({'name': config.name, 'shard': str(i)})
json.dump(output, sys.stdout, indent=4)
print()
