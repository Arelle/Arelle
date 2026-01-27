from __future__ import annotations

from collections import defaultdict

import csv
import difflib
import json
import statistics
from dataclasses import dataclass
from heapq import heapreplace
from pathlib import Path
from typing import Any, TYPE_CHECKING, cast

from arelle.testengine.Constraint import Constraint
from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.TestcaseSet import TestcaseSet
from tests.integration_tests.integration_test_util import get_test_data
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


CONFORMANCE_SUITE_EXPECTED_RESOURCES_DIRECTORY = Path('tests/resources/conformance_suites_expected')
CONFORMANCE_SUITE_TIMING_RESOURCES_DIRECTORY = Path('tests/resources/conformance_suites_timing')


def get_test_data_mp_wrapper(args_kws: tuple[TestEngineOptions, dict[str, Any]]) -> list[ParameterSet]:
    args, kws = args_kws
    return get_test_data(args, **kws)


def get_test_shards(config: ConformanceSuiteConfig, testcase_set: TestcaseSet, shard_count: int) -> list[list[str]]:

    @dataclass(frozen=True)
    class PathInfo:
        test_id: str
        runtime: float
    path_infos: list[PathInfo] = []
    approximate_relative_timing = load_timing_file(config.name)
    test_ids = [testcase.full_id for testcase in testcase_set.testcases]
    for test_id in test_ids:
        testcase_runtime = approximate_relative_timing.get(test_id, 1)
        path_infos.append(PathInfo(
            test_id=test_id,
            runtime=testcase_runtime,
        ))
    paths_in_runtime_order: list[PathInfo] = sorted(
        path_infos,
        key=lambda p: p.runtime,
        reverse=True
    )
    runtime_paths: list[tuple[float, list[str]]] = [(0, []) for _ in range(shard_count)]
    for path in paths_in_runtime_order:
        shard_runtime, shard = runtime_paths[0]
        shard.append(path.test_id)
        heapreplace(runtime_paths, (shard_runtime + path.runtime, shard))
    return _build_shards(runtime_paths)


def _build_shards(runtime_paths: list[tuple[float, list[str]]]) -> list[list[str]]:
    # Sort shards by runtime so CI nodes are more likely to pick shards with similar runtimes.
    time_ordered_shards = sorted(runtime_paths)
    return [
        test_ids
        for __, test_ids in time_ordered_shards
    ]


def get_conformance_suite_test_results(
        config: ConformanceSuiteConfig,
        testcase_set: TestcaseSet,
        shard_count: int,
        shards: list[int],
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False,
        series: bool = False,
        testcase_filters: list[str] | None = None,
) -> list[ParameterSet]:
    assert len(shards) == 0 or shard_count != 1, \
        'Must specify shard count if --shard is passed'
    if shards:
        # assert not testcase_filters, 'Testcase filters are not supported with shards.'
        return get_conformance_suite_test_results_with_shards(
            config=config, testcase_set=testcase_set, shard_count=shard_count, shards=shards, build_cache=build_cache, log_to_file=log_to_file, offline=offline, series=series
        )
    else:
        return get_conformance_suite_test_results_without_shards(
            config=config, testcase_set=testcase_set, build_cache=build_cache, log_to_file=log_to_file, offline=offline, series=series, testcase_filters=testcase_filters
        )


def _get_additional_constraints(config: ConformanceSuiteConfig) -> list[tuple[str, list[Constraint]]]:
    additional_constraints = []
    for test_id, errors in config.expected_additional_testcase_errors.items():
        additional_constraints.append(
            (
                test_id,
                [
                    Constraint(
                        qname=None,
                        pattern=code,
                        count=count,
                    )
                    for code, count in errors.items()
                ],
            )
        )
    return additional_constraints


def _get_disclosure_system_by_id_map(disclosure_system_by_prefix: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [
        (f'{prefix}*', disclosure_system)
        for prefix, disclosure_system in disclosure_system_by_prefix
    ]


def _get_plugins_by_id_map(additional_plugins_by_prefix: list[tuple[str, frozenset[str]]]) -> list[tuple[str, frozenset[str]]]:
    return [
        (f'{prefix}*', plugins)
        for prefix, plugins in additional_plugins_by_prefix
    ]


def get_conformance_suite_test_results_with_shards(
        config: ConformanceSuiteConfig,
        testcase_set: TestcaseSet,
        shard_count: int,
        shards: list[int],
        build_cache: bool,
        log_to_file: bool,
        offline: bool,
        series: bool) -> list[ParameterSet]:
    tasks = []
    all_testcase_filters = []
    test_shards = get_test_shards(config, testcase_set, shard_count)
    for shard_id in shards:
        shard_test_ids = test_shards[shard_id]
        all_testcase_filters.extend(shard_test_ids)

        runtime_options = get_runtime_options(
            config=config, build_cache=build_cache, offline=offline, shard=shard_id,
        )
        test_engine_options = TestEngineOptions(
            additional_constraints=_get_additional_constraints(config),
            compare_formula_output=config.compare_formula_output,
            custom_compare_patterns=config.custom_compare_patterns,
            disclosure_system_by_id=_get_disclosure_system_by_id_map(config.disclosure_system_by_prefix),
            filters=shard_test_ids,
            ignore_levels=config.ignore_levels,
            index_file=config.entry_point_path,
            log_directory=(Path('conf-logs') / config.name) if log_to_file else None,
            match_all=config.test_case_result_options == 'match-all',
            name=config.name,
            options=runtime_options,
            plugins_by_id=_get_plugins_by_id_map(config.additional_plugins_by_prefix),
            parallel=not series, # "daemonic processes are not allowed to have children"
        )
        kws = dict(
            testcase_set=testcase_set,
            expected_failure_ids=config.expected_failure_ids,
            required_locale_by_ids=config.required_locale_by_ids,
        )
        tasks.append((test_engine_options, kws))
    results = []
    for task in tasks:
        task_results = get_test_data_mp_wrapper(task)
        results.extend(task_results)
    merged_results: dict[str, ParameterSet] = {}
    for result in results:
        result_id = str(result.id)
        values = cast(dict[str, Any], result.values[0])
        status = values.get('status')
        existing_result = merged_results.get(result_id)
        if existing_result is None:
            merged_results[result_id] = result
        elif status != 'skip':
            existing_values = cast(dict[str, Any], existing_result.values[0])
            existing_status = existing_values.get('status')
            assert existing_status == 'skip', \
                f'Conflicting results for {result_id}: {existing_status} vs {status}'
            merged_results[result_id] = result
    results = list(sorted(merged_results.values(), key=lambda x: str(x.id)))

    assert sum(1 for r in results if cast(dict[str, Any], r.values[0]).get('status') != 'skip') == len(all_testcase_filters), \
        f'Expected {len(all_testcase_filters)} results based on testcase filters, received {len(results)}'

    return results


def get_conformance_suite_test_results_without_shards(
        config: ConformanceSuiteConfig,
        testcase_set: TestcaseSet,
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False,
        series: bool = False,
        testcase_filters: list[str] | None = None,
) -> list[ParameterSet]:
    runtime_options = get_runtime_options(
        config=config, build_cache=build_cache, offline=offline, shard=None,
    )
    return get_test_data(
        test_engine_options=TestEngineOptions(
            additional_constraints=_get_additional_constraints(config),
            compare_formula_output=config.compare_formula_output,
            custom_compare_patterns=config.custom_compare_patterns,
            disclosure_system_by_id=_get_disclosure_system_by_id_map(config.disclosure_system_by_prefix),
            filters=testcase_filters or [],
            ignore_levels=config.ignore_levels,
            index_file=config.entry_point_path,
            log_directory=(Path('conf-logs') / config.name) if log_to_file else None,
            match_all=config.test_case_result_options == 'match-all',
            name=config.name,
            options=runtime_options,
            plugins_by_id=_get_plugins_by_id_map(config.additional_plugins_by_prefix),
            parallel=not series,
        ),
        testcase_set=testcase_set,
        expected_failure_ids=config.expected_failure_ids,
        required_locale_by_ids=config.required_locale_by_ids,
    )


def get_runtime_options(
        config: ConformanceSuiteConfig,
        build_cache: bool,
        offline: bool,
        shard: int | None,
) -> dict[str, Any]:
    use_shards = shard is not None
    optional_plugins = set()
    if build_cache:
        optional_plugins.add('CacheBuilder')
    plugins = config.plugins | optional_plugins
    args: dict[str, Any] = {}
    plugin_options = {}
    if config.base_taxonomy_validation:
        args['baseTaxonomyValidationMode'] = config.base_taxonomy_validation
    if config.disclosure_system:
        args['disclosureSystemName'] = config.disclosure_system
    if config.package_paths:
        args['packages'] = sorted(str(p) for p in config.package_paths)
    if plugins:
        args['plugins'] = '|'.join(sorted(plugins))
    shard_str = f'-s{shard}' if use_shards else ''
    if build_cache:
        plugin_options['cacheBuilderPath'] = f'conf-{config.name}{shard_str}-cache.zip'
    if config.capture_warnings:
        args['testcaseResultsCaptureWarnings'] = True
    if offline or config.runs_without_network:
        args['internetConnectivity'] = 'offline'
    args['pluginOptions'] = plugin_options
    for k, v in config.runtime_options.items():
        if k not in args:
            args[k] = v
        elif isinstance(v, dict):
            args[k] |= v
        elif isinstance(v, list):
            args[k] += v
        else:
            args[k] = v
    return args


def load_timing_file(name: str) -> dict[str, float]:
    path = CONFORMANCE_SUITE_TIMING_RESOURCES_DIRECTORY / Path(name).with_suffix('.json')
    if not path.exists():
        return {}
    with open(path) as file:
        data = json.load(file)
        return {
            str(k): float(v)
            for k, v in data.items()
        }


def save_actual_results_file(config: ConformanceSuiteConfig, results: list[ParameterSet]) -> Path:
    """
    Saves a CSV file with format "(Full testcase variation ID),(Code)".
    Each row represents a unique code actually triggered by a variation.
    If an expected results file exists for the given conformance suite config,
    the actual results file is then compared to the expected results file and an
    HTML diff file is generated so that differences can be reviewed.
    :param config: The conformance suite config associated with the given results.
    :param results: The full set of results from a conformance suite run.
    :return: Path to the saved file
    """
    rows = []
    for result in results:
        testcase_id = result.id
        actual_json = cast(dict[str, str], result.values[0]).get('actual') or '{}'
        actual_codes = json.loads(actual_json)
        for code, count in actual_codes.items():
            rows.append((testcase_id, code, count))
    output_filepath = Path(f'conf-{config.name}-actual.csv')
    with open(output_filepath, 'w') as file:
        writer = csv.writer(file)
        writer.writerows(sorted(rows))
    return output_filepath


def save_diff_html_file(expected_results_path: Path, actual_results_path: Path, output_path: Path) -> None:
    with open(expected_results_path) as file:
        expected_rows = [row for row in file]
    with open(actual_results_path) as file:
        actual_rows = [row for row in file]
    html = difflib.HtmlDiff().make_file(
        expected_rows, actual_rows,
        fromdesc='Expected', todesc='Actual', context=True, numlines=6
    )
    with open(output_path, 'w') as file:
        file.write(html)


def save_timing_file(config: ConformanceSuiteConfig, results: list[ParameterSet]) -> None:
    durations: dict[str, float] = defaultdict(float)
    for result in results:
        testcase_id = result.id
        assert isinstance(testcase_id, str)
        values = cast(dict[str, Any], result.values[0])
        status = values.get('status')
        assert status, f'Test result has no status: {testcase_id}'
        if status == 'skip':
            continue
        assert testcase_id and testcase_id not in durations
        duration = values.get('duration')
        if duration:
            durations[testcase_id] = duration
    if durations:
        duration_values = durations.values()
        duration_mean = statistics.mean(duration_values)
        duration_stdev = statistics.stdev(duration_values) if len(duration_values) > 1 else 0
        durations = {
            testcase_id: duration/duration_mean
            for testcase_id, duration in sorted(durations.items())
        }
        durations['<mean>'] = duration_mean
        durations['<stdev>'] = duration_stdev
    with open(f'conf-{config.name}-timing.json', 'w') as file:
        json.dump(durations, file, indent=4)
