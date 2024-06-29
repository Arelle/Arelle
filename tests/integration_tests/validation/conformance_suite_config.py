from __future__ import annotations

import itertools
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Literal


CONFORMANCE_SUITE_PATH_PREFIX = 'tests/resources/conformance_suites'


class AssetSource(Enum):
    LOCAL = 1
    S3_PUBLIC = 2
    S3_PRIVATE = 3

    def is_s3(self) -> bool:
        return self in (AssetSource.S3_PUBLIC, AssetSource.S3_PRIVATE)


class AssetType(Enum):
    CONFORMANCE_SUITE = 1
    CACHE_PACKAGE = 2
    TAXONOMY_PACKAGE = 3


@dataclass(frozen=True)
class ConformanceSuiteAssetConfig:
    local_filename: Path
    source: AssetSource
    type: AssetType
    extract_sequence: tuple[tuple[Path, Path], ...] = field(default_factory=tuple)
    entry_point: Path | None = field(compare=False, default=None)
    entry_point_root: Path | None = None
    public_download_url: str | None = None
    s3_key: str | None = None
    s3_version_id: str | None = None

    def __post_init__(self) -> None:
        if self.source.is_s3():
            assert self.s3_key is not None, 'Must provide S3 key for S3 assets.'
        else:
            assert self.s3_key is None, \
                'S3 key must not be provided for non-S3 assets.'
            assert self.s3_version_id is None, \
                'S3 version ID must not be provided for non-S3 assets.'
        assert bool(self.entry_point) == bool(self.entry_point_root),\
            'Entry point and entry point root must be both None or both set.'

    @cached_property
    def local_directory(self) -> Path:
        if self.type == AssetType.CONFORMANCE_SUITE:
            return Path('tests/resources/conformance_suites')
        if self.type == AssetType.TAXONOMY_PACKAGE:
            return Path('tests/resources/packages')
        return Path('tests/resources')

    @cached_property
    def full_entry_point(self) -> Path | None:
        if not self.full_entry_point_root or not self.entry_point:
            return None
        return self.full_entry_point_root / self.entry_point

    @cached_property
    def full_entry_point_root(self) -> Path | None:
        if not self.entry_point_root:
            return None
        return self.local_directory / self.entry_point_root

    @cached_property
    def full_local_path(self) -> Path:
        return self.local_directory / self.local_filename

    def get_conflicting_directories(self, reserved_directories: set[Path]) -> dict[Path, set[Path]]:
        return {
            k: v
            for k, v in {
                reserved_path: {
                    d for d in reserved_directories if d in reserved_path.parents
                }
                for reserved_path in self.full_reserved_paths
            }.items()
            if v
        }

    def get_conflicting_paths(self, reserved_paths: set[Path]) -> set[Path]:
        return reserved_paths.intersection(self.full_reserved_paths)

    @cached_property
    def full_reserved_directories(self) -> set[Path]:
        """
        :return: Set of directory paths this asset will write to.
        """
        return {
            self.local_directory / extract_to
            for __, extract_to in self.extract_sequence
        }

    @cached_property
    def full_reserved_paths(self) -> set[Path]:
        """
        :return: Set of file paths this asset will read from or write to.
        """
        return {
            self.full_local_path,
            self.full_entry_point_root or self.full_local_path,
        } | {
            self.local_directory / extract_from for extract_from, __ in self.extract_sequence
        }

    @staticmethod
    def cache_package(name: str, s3_version_id: str) -> ConformanceSuiteAssetConfig:
        return ConformanceSuiteAssetConfig(
            local_filename=Path(f'temp-{name}-cache.zip'),
            source=AssetSource.S3_PUBLIC,
            type=AssetType.CACHE_PACKAGE,
            s3_key=f'{name}.zip',
            s3_version_id=s3_version_id,
        )

    @staticmethod
    def conformance_suite(
            name: Path,
            entry_point: Path | None = None,
            public_download_url: str | None = None,
            source: AssetSource = AssetSource.S3_PRIVATE) -> ConformanceSuiteAssetConfig:
        return ConformanceSuiteAssetConfig(
            local_filename=name,
            source=source,
            type=AssetType.CONFORMANCE_SUITE,
            entry_point=entry_point,
            entry_point_root=name if entry_point else None,
            public_download_url=public_download_url,
            s3_key=name.as_posix() if source.is_s3() else None,
        )

    @staticmethod
    def local_conformance_suite(
            name: Path,
            entry_point: Path | None = None) -> ConformanceSuiteAssetConfig:
        return ConformanceSuiteAssetConfig(
            local_filename=name,
            source=AssetSource.LOCAL,
            type=AssetType.CONFORMANCE_SUITE,
            entry_point=entry_point,
            entry_point_root=name if entry_point else None,
        )

    @staticmethod
    def nested_conformance_suite(
            name: Path,
            extract_to: Path,
            entry_point_root: Path,
            entry_point: Path,
            public_download_url: str | None = None,
            source: AssetSource = AssetSource.S3_PRIVATE) -> ConformanceSuiteAssetConfig:
        return ConformanceSuiteAssetConfig(
            local_filename=name,
            source=source,
            type=AssetType.CONFORMANCE_SUITE,
            entry_point=entry_point,
            entry_point_root=entry_point_root,
            extract_sequence=(
                (name, extract_to),
            ),
            public_download_url=public_download_url,
            s3_key=name.as_posix() if source.is_s3() else None,
        )

    @staticmethod
    def public_taxonomy_package(name: Path, public_download_url: str | None = None) -> ConformanceSuiteAssetConfig:
        return ConformanceSuiteAssetConfig(
            local_filename=name,
            source=AssetSource.S3_PUBLIC,
            type=AssetType.TAXONOMY_PACKAGE,
            public_download_url=public_download_url,
            s3_key=name.as_posix(),
        )


@dataclass(frozen=True)
class ConformanceSuiteConfig:
    info_url: str
    name: str
    additional_plugins_by_prefix: list[tuple[str, frozenset[str]]] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    assets: list[ConformanceSuiteAssetConfig] = field(default_factory=list)
    cache_version_id: str | None = None
    capture_warnings: bool = True
    ci_enabled: bool = True
    expected_failure_ids: frozenset[str] = frozenset()
    expected_missing_testcases: frozenset[str] = frozenset()
    expected_model_errors: frozenset[str] = frozenset()
    membership_url: str | None = None
    plugins: frozenset[str] = frozenset()
    shards: int = 1
    strict_testcase_index: bool = True
    url_replace: str | None = None
    network_or_cache_required: bool = True
    required_locale_by_ids: dict[str, re.Pattern[str]] = field(default_factory=dict)
    test_case_result_options: Literal['match-all', 'match-any'] = 'match-all'

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
        overlapping_expected_testcase_ids = self.expected_failure_ids.intersection(self.required_locale_by_ids)
        assert not overlapping_expected_testcase_ids, \
            f'Testcase IDs in both expected failures and required locales: {sorted(overlapping_expected_testcase_ids)}'
        assert not self.network_or_cache_required or self.package_paths or self.cache_version_id, \
            'If network or cache is required, either packages must be used or a cache version ID must be provided.'

    @cached_property
    def entry_point_asset(self) -> ConformanceSuiteAssetConfig:
        entry_points = [asset for asset in self.assets if asset.entry_point]
        assert len(entry_points) == 1, \
            'Exactly one asset with entry point must be configured.'
        return entry_points[0]

    @cached_property
    def entry_point_path(self) -> Path:
        full_entry_point = self.entry_point_asset.full_entry_point
        assert full_entry_point is not None
        return full_entry_point

    @cached_property
    def entry_point_root(self) -> Path:
        entry_point_root = self.entry_point_asset.full_entry_point_root
        assert entry_point_root is not None
        return entry_point_root

    @cached_property
    def has_private_asset(self) -> bool:
        return any(asset.source == AssetSource.S3_PRIVATE for asset in self.assets)

    @cached_property
    def package_paths(self) -> set[Path]:
        return {
            asset.full_local_path
            for asset in self.assets
            if asset.type == AssetType.TAXONOMY_PACKAGE
        }
