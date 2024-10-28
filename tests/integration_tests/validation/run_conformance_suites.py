from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any, TYPE_CHECKING

from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig
)
from tests.integration_tests.validation.conformance_suite_configs import (
    ALL_CONFORMANCE_SUITE_CONFIGS,
    PUBLIC_CONFORMANCE_SUITE_CONFIGS
)
from tests.integration_tests.validation.download_assets import download_assets, verify_assets
from tests.integration_tests.validation.validation_util import get_conformance_suite_test_results, save_timing_file
from tests.integration_tests.validation.validation_util import (
    save_actual_results_file,
    CONFORMANCE_SUITE_EXPECTED_RESOURCES_DIRECTORY, save_diff_html_file
)

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


ARGUMENTS: list[dict[str, Any]] = [
    {
        "name": "--all",
        "action": "store_true",
        "help": "Select all configured conformance suites"
    },
    {
        "name": "--build-cache",
        "action": "store_true",
        "help": "Use CacheBuilder plugin to build cache from conformance suite usage"
    },
    {
        "name": "--download-cache",
        "action": "store_true",
        "help": "Download and apply pre-built cache package and taxonomy packages"
    },
    {
        "name": "--download-overwrite",
        "action": "store_true",
        "help": "Download (and overwrite) selected conformance suite files"
    },
    {
        "name": "--download-missing",
        "action": "store_true",
        "help": "Download missing selected conformance suite files"
    },
    {
        "name": "--download-private",
        "action": "store_true",
        "help": "Download privately hosted assets (AWS CLI and environment variables required)"
    },
    {
        "name": "--list",
        "action": "store_true",
        "help": "List names of all configured conformance suites"
    },
    {
        "name": "--log-to-file",
        "action": "store_true",
        "help": "Writes logs and results to .txt and .csv files"
    },
    {
        "name": "--name",
        "action": "store",
        "help": "Select only conformance suites with given names, comma delimited"
    },
    {
        "name": "--offline",
        "action": "store_true",
        "help": "Run without loading anything from the internet (local files and cache only)"
    },
    {
        "name": "--public",
        "action": "store_true",
        "help": "Select all public conformance suites"
    },
    {
        "name": "--series",
        "action": "store_true",
        "help": "Run shards in series"
    },
    {
        "name": "--shard",
        "action": "store",
        "help": "comma separated list of 0-indexed shards to run",
    },
    {
        "name": "--test",
        "action": "store_true",
        "help": "Run selected conformance suite tests"
    },
]
DOWNLOAD_MISSING = 'missing'
DOWNLOAD_OVERWRITE = 'overwrite'
SELECT_ALL = 'all'
SELECT_PUBLIC = 'public'


def _get_conformance_suite_names(select_option: str) -> tuple[ConformanceSuiteConfig, ...]:
    if select_option == SELECT_ALL:
        return ALL_CONFORMANCE_SUITE_CONFIGS
    elif select_option == SELECT_PUBLIC:
        return PUBLIC_CONFORMANCE_SUITE_CONFIGS
    elif select_option:
        filter_list = select_option.split(',')
        names = []
        for filter_item in filter_list:
            match_configs = [c for c in ALL_CONFORMANCE_SUITE_CONFIGS if c.name == filter_item]
            if not match_configs:
                raise ValueError(f'Provided name "{filter_item}" did not match any configured conformance suite names.')
            names.extend(match_configs)
        return tuple(names)
    else:
        raise ValueError('Please use --all, --public, or --name to specify which conformance suites to use.')


def run_conformance_suites(
        select_option: str,
        test_option: bool,
        shard: str,
        build_cache: bool = False,
        download_cache: bool = False,
        download_option: str | None = None,
        download_private: bool = False,
        log_to_file: bool = False,
        offline_option: bool = False,
        series_option: bool = False) -> list[ParameterSet]:
    conformance_suite_configs = _get_conformance_suite_names(select_option)
    unique_assets = set()
    for config in conformance_suite_configs:
        if config.cache_version_id:
            unique_assets.add(ConformanceSuiteAssetConfig.cache_package(config.name, config.cache_version_id))
        unique_assets.update(tuple(config.assets))
    if download_option:
        download_assets(unique_assets, download_option == DOWNLOAD_OVERWRITE, download_cache, download_private)
    else:
        verify_assets(unique_assets)
    all_results = []
    if test_option:
        for config in conformance_suite_configs:
            shards: list[int] = []
            full_run = True
            if shard:
                for part in shard.split(','):
                    if '-' in part:
                        start, end = part.split('-')
                        shards.extend(range(int(start), int(end) + 1))
                    else:
                        shards.append(int(part))
                full_run = set(shards) == set(range(0, config.shards))
            results = get_conformance_suite_test_results(
                config,
                shards=shards,
                build_cache=build_cache,
                log_to_file=log_to_file,
                offline=offline_option,
                series=series_option,
            )
            if log_to_file:
                save_timing_file(config, results)
                actual_results_path = save_actual_results_file(config, results)
                if full_run:
                    expected_results_path = CONFORMANCE_SUITE_EXPECTED_RESOURCES_DIRECTORY / Path(config.name).with_suffix('.csv')
                    if expected_results_path.exists():
                        save_diff_html_file(expected_results_path, actual_results_path, Path(f'conf-{config.name}-diff.html'))
            all_results.extend(results)
    return all_results


def run_conformance_suites_options(options: Namespace) -> list[ParameterSet]:
    select_option = get_select_option(options)
    download_option = get_download_option(options)
    assert download_option or options.test, \
        'Specify at least one of download, list, or test.'
    assert download_option or not options.download_private, \
        'Private download must only be enabled if download option is provided.'
    return run_conformance_suites(
        select_option=select_option,
        test_option=options.test,
        shard=options.shard,
        build_cache=options.build_cache,
        download_option=download_option,
        download_private=options.download_private,
        download_cache=options.download_cache,
        log_to_file=options.log_to_file,
        offline_option=options.offline,
        series_option=options.series,
    )


def get_download_option(options: Namespace) -> str | None:
    if options.download_overwrite:
        return DOWNLOAD_OVERWRITE
    elif options.download_missing:
        return DOWNLOAD_MISSING
    return None


def get_select_option(options: Namespace) -> str:
    if options.all:
        return SELECT_ALL
    elif options.public:
        return SELECT_PUBLIC
    assert isinstance(options.name, str)
    return options.name


def run() -> None:
    parser = ArgumentParser(prog=sys.argv[0])
    for arg in ARGUMENTS:
        arg_without_name = {k: v for k, v in arg.items() if k != "name"}
        parser.add_argument(arg["name"], **arg_without_name)
    options = parser.parse_args(sys.argv[1:])
    if options.list:
        for config in ALL_CONFORMANCE_SUITE_CONFIGS:
            print(f'{config.name}\n'
                  f'\tInfo:       {config.info_url}\n'
                  f'\tDownload:   {config.entry_point_asset.public_download_url or config.membership_url}\n'
                  f'\tEntry Point: {config.entry_point_path}')
    else:
        run_conformance_suites_options(options)


if __name__ == "__main__":
    run()
