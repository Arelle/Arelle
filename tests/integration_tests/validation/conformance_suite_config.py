from __future__ import annotations

import itertools
import os
from dataclasses import dataclass, field


CONFORMANCE_SUITE_PATH_PREFIX = 'tests/resources/conformance_suites'


@dataclass(frozen=True)
class ConformanceSuiteConfig:
    file: str
    info_url: str
    local_filepath: str
    name: str
    additional_downloads: dict[str, str] = field(default_factory=dict)
    additional_plugins_by_prefix: list[tuple[str, frozenset[str]]] = field(default_factory=list)
    approximate_relative_timing: dict[str, float] = field(default_factory=dict)  # by uri
    args: list[str] = field(default_factory=list)
    capture_warnings: bool = True
    expected_empty_testcases: frozenset[str] = frozenset()
    expected_failure_ids: frozenset[str] = frozenset()
    expected_model_errors: frozenset[str] = frozenset()
    extract_path: str | None = None
    membership_url: str | None = None
    plugins: frozenset[str] = frozenset()
    public_download_url: str | None = None
    shards: int = 1
    url_replace: str | None = None

    def __post_init__(self) -> None:
        redundant_plugins = [(prefix, overlap)
            for prefix, additional_plugins in self.additional_plugins_by_prefix
            for overlap in [self.plugins & additional_plugins]
            if overlap]
        assert not redundant_plugins, \
            f'Plugins specified both as default and additional: {redundant_plugins}'
        overlapping_prefixes = [(p1, p2)
            for (p1, _), (p2, _) in itertools.combinations(self.additional_plugins_by_prefix, 2)
            if p1.startswith(p2) or p2.startswith(p1)]
        assert not overlapping_prefixes, \
            f'Overlapping prefixes are not supported: {overlapping_prefixes}'
        assert not (self.shards == 1 and self.additional_plugins_by_prefix), \
            'Cannot specify additional_plugins_by_prefix with only one shard.'
        plugin_combinations = len({plugins for _, plugins in self.additional_plugins_by_prefix}) + 1
        assert plugin_combinations <= self.shards, \
            'Too few shards to accommodate the number of plugin combinations:' \
            f' combinations={plugin_combinations} shards={self.shards}'

    @property
    def prefixed_extract_filepath(self) -> str | None:
        if self.extract_path is None:
            return None
        return os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, self.extract_path)

    @property
    def prefixed_local_filepath(self) -> str:
        return os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, self.local_filepath)
