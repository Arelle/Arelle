from __future__ import annotations

import fnmatch
from collections import defaultdict, Counter

import sys
from argparse import ArgumentParser, Namespace
from dataclasses import replace
from pathlib import Path
from typing import Any, TYPE_CHECKING

from arelle.testengine.TestEngine import load_testcase_index
from arelle.testengine.TestcaseSet import TestcaseSet
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
        "name": "--shard-count",
        "action": "store",
        "help": "number of shards to split suite into",
    },
    {
        "name": "--test",
        "action": "store_true",
        "help": "Run selected conformance suite tests"
    },
    {
        "name": "--testcase-filter",
        "action": "append",
        "help": "Filter test cases (see --testcaseFilter)",
    }
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
        shard_count: int | None,
        shard: str | None,
        build_cache: bool = False,
        download_cache: bool = False,
        download_option: str | None = None,
        download_private: bool = False,
        log_to_file: bool = False,
        offline_option: bool = False,
        series_option: bool = False,
        testcase_filters: list[str] | None = None,
) -> list[ParameterSet]:
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
    preload_errors: dict[str, list[str]] = {}
    for config in conformance_suite_configs:
        testcase_set = preload_testcase_set(config)
        if testcase_set.load_errors:
            preload_errors[config.name] = testcase_set.load_errors
        if not test_option:
            continue
        assert not testcase_set.load_errors, \
            (f"Errors were encountered while loading the '{config.name}' "
             f"conformance suite: {testcase_set.load_errors}")
        shards: list[int] = []
        config_shard_count = shard_count or config.ci_config.shard_count
        full_run = True
        if shard:
            for part in shard.split(','):
                if '-' in part:
                    start, end = part.split('-')
                    shards.extend(range(int(start), int(end) + 1))
                else:
                    shards.append(int(part))
            full_run = set(shards) == set(range(0, config_shard_count))
        results = get_conformance_suite_test_results(
            config,
            testcase_set,
            shard_count=config_shard_count,
            shards=shards,
            build_cache=build_cache,
            log_to_file=log_to_file,
            offline=offline_option,
            series=series_option,
            testcase_filters=testcase_filters,
        )
        if log_to_file:
            save_timing_file(config, results)
            actual_results_path = save_actual_results_file(config, results)
            if full_run:
                expected_results_path = CONFORMANCE_SUITE_EXPECTED_RESOURCES_DIRECTORY / Path(config.name).with_suffix('.csv')
                if expected_results_path.exists():
                    save_diff_html_file(expected_results_path, actual_results_path, Path(f'conf-{config.name}-diff.html'))
        all_results.extend(results)
    assert not preload_errors, \
        f"Conformance suite misconfigurations detected during preloading of testcases: {preload_errors}"
    return all_results


def get_nonexistent_test_ids(expected_test_ids : frozenset[str], actual_test_ids: frozenset[str]) -> frozenset[str]:
    # Eliminate exact matches first
    nonexistent_test_ids = expected_test_ids - actual_test_ids
    if nonexistent_test_ids:
        # Eliminate pattern matches
        nonexistent_test_ids = frozenset({
            _id
            for _id in nonexistent_test_ids
            if not any(fnmatch.fnmatch(test_id, _id) for test_id in actual_test_ids)
        })
    return nonexistent_test_ids



def preload_testcase_set(config: ConformanceSuiteConfig) -> TestcaseSet:
    testcase_set = load_testcase_index(config.entry_point_path)

    if config.preprocessing_func is not None:
        testcase_set = config.preprocessing_func(config, testcase_set)

    load_errors = list(testcase_set.load_errors)

    all_test_ids = [t.full_id for t in testcase_set.testcases]

    test_id_frequencies = Counter(all_test_ids)
    nonunique_test_ids = {test_id: count for test_id, count in sorted(test_id_frequencies.items()) if count > 1}
    if nonunique_test_ids:
        load_errors.append(f"Some test IDs are not unique.  Frequencies of nonunique test IDs: {nonunique_test_ids}.")

    unique_test_ids = frozenset(all_test_ids)

    nonexistent_expected_failure_ids = get_nonexistent_test_ids(config.expected_failure_ids, unique_test_ids)
    if nonexistent_expected_failure_ids:
        load_errors.append(f"Some expected failure IDs don't match any test cases: {sorted(nonexistent_expected_failure_ids)}.")

    nonexistent_expected_additional_testcase_errors = get_nonexistent_test_ids(frozenset(config.expected_additional_testcase_errors), unique_test_ids)
    if nonexistent_expected_additional_testcase_errors:
        load_errors.append(f"Some additional error IDs don't match any test cases: {sorted(nonexistent_expected_additional_testcase_errors)}")

    nonexistent_required_locale_testcase_ids = get_nonexistent_test_ids(frozenset(config.required_locale_by_ids), unique_test_ids)
    if nonexistent_required_locale_testcase_ids:
        load_errors.append(f"Some required locale IDs don't match any test cases: {sorted(nonexistent_required_locale_testcase_ids)}.")

    nonexistent_additional_plugin_prefixes = get_nonexistent_test_ids(frozenset(f"{p}*" for p, __ in config.additional_plugins_by_prefix), unique_test_ids)
    if nonexistent_additional_plugin_prefixes:
        load_errors.append(f"Some additional plugin prefix patterns don't match any test cases: {sorted(nonexistent_additional_plugin_prefixes)}")

    nonexistent_disclosure_system_prefixes = get_nonexistent_test_ids(frozenset(f"{p}*" for p, __ in config.disclosure_system_by_prefix), unique_test_ids)
    if nonexistent_disclosure_system_prefixes:
        load_errors.append(f"Some disclosure system prefix patterns don't match any test cases: {sorted(nonexistent_disclosure_system_prefixes)}")

    filtered_load_errors = []
    matched_expected_load_errors = set()
    for load_error in load_errors:
        load_error = load_error.replace('\\', '/')
        if load_error in config.expected_load_errors:
            matched_expected_load_errors.add(load_error)
            continue
        matched = False
        for pattern in config.expected_load_errors:
            if fnmatch.fnmatch(load_error, pattern):
                matched_expected_load_errors.add(pattern)
                matched = True
                break
        if not matched:
            filtered_load_errors.append(load_error)

    nonexistent_expected_load_errors = config.expected_load_errors - matched_expected_load_errors
    if nonexistent_expected_load_errors:
        load_errors.append(f"Some expected load errors don't match any actual load errors: {sorted(nonexistent_expected_load_errors)}")

    return replace(testcase_set, load_errors=filtered_load_errors)


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
        shard_count=int(options.shard_count) if options.shard_count else None,
        shard=options.shard,
        build_cache=options.build_cache,
        download_option=download_option,
        download_private=options.download_private,
        download_cache=options.download_cache,
        log_to_file=options.log_to_file,
        offline_option=options.offline,
        series_option=options.series,
        testcase_filters=options.testcase_filter
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
