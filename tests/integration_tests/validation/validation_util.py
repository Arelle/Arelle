from __future__ import annotations

import csv
import difflib
import json
import multiprocessing
import os.path
import statistics
import zipfile
from collections import defaultdict
from collections.abc import Generator
from contextlib import nullcontext
from dataclasses import dataclass
from heapq import heapreplace
from pathlib import PurePosixPath, Path
from typing import Any, Callable, ContextManager, TYPE_CHECKING, cast
from unittest.mock import patch

from lxml import etree

from arelle.WebCache import WebCache
from tests.integration_tests.integration_test_util import get_test_data
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


original_normalize_url_function = WebCache.normalizeUrl
CONFORMANCE_SUITE_EXPECTED_RESOURCES_DIRECTORY = Path('tests/resources/conformance_suites_expected')
CONFORMANCE_SUITE_TIMING_RESOURCES_DIRECTORY = Path('tests/resources/conformance_suites_timing')


@dataclass(frozen=True)
class Shard:
    paths: dict[str, list[str]]
    plugins: frozenset[str]


def normalize_url_function(config: ConformanceSuiteConfig) -> Callable[[WebCache, str, str | None], str]:
    def normalize_url(self: WebCache, url: str, base: str | None = None) -> str:
        assert config.url_replace is not None
        if url.startswith(config.url_replace):
            return url.replace(config.url_replace, f'{config.entry_point_root}/')
        return cast(str, original_normalize_url_function(self, url, base))
    return normalize_url


def get_test_data_mp_wrapper(args_kws: tuple[list[Any], dict[str, Any]]) -> list[ParameterSet]:
    args, kws = args_kws
    return get_test_data(args, **kws)


def get_testcase_variation_map(config: ConformanceSuiteConfig) -> dict[str, list[str]]:
    test_case_paths: list[str] = []

    entry_point_root = str(config.entry_point_root)

    entry_point = config.entry_point_asset.entry_point
    assert entry_point is not None
    entry_point_str = entry_point.as_posix()

    if zipfile.is_zipfile(entry_point_root):
        with zipfile.ZipFile(entry_point_root) as zip_file:
            _collect_zip_test_cases(zip_file, entry_point_str, test_case_paths, config.expected_missing_testcases)
            return _collect_zip_test_case_variation_ids(zip_file, test_case_paths)
    else:
        _collect_dir_test_cases(entry_point_root, entry_point_str, test_case_paths)
        return _collect_dir_test_case_variation_ids(entry_point_root, test_case_paths)


def get_test_shards(config: ConformanceSuiteConfig) -> list[Shard]:
    testcase_variation_map = get_testcase_variation_map(config)
    assert testcase_variation_map

    @dataclass(frozen=True)
    class PathInfo:
        path: tuple[str, str]
        plugins: tuple[str, ...]
        runtime: float
    paths_by_plugins: dict[tuple[str, ...], list[PathInfo]] = defaultdict(list)
    approximate_relative_timing = load_timing_file(config.name)
    empty_testcase_paths: set[str] = set()
    for testcase_path, variation_ids in testcase_variation_map.items():
        if not variation_ids:
            empty_testcase_paths.add(testcase_path)
            continue
        path_plugins: set[str] = set()
        for prefix, additional_plugins in config.additional_plugins_by_prefix:
            if testcase_path.startswith(prefix):
                path_plugins.update(additional_plugins)
        testcase_runtime = approximate_relative_timing.get(testcase_path, 1)
        avg_variation_runtime = testcase_runtime/(len(variation_ids))  # compatability for testcase-level timing
        for variation_id in variation_ids:
            variation_runtime = approximate_relative_timing.get(f'{testcase_path}:{variation_id}', avg_variation_runtime)
            paths_by_plugins[tuple(path_plugins)].append(PathInfo(
                path=(testcase_path, variation_id),
                plugins=tuple(path_plugins),
                runtime=variation_runtime,
            ))
    paths_in_runtime_order: list[PathInfo] = sorted((path for paths in paths_by_plugins.values() for path in paths),
        key=lambda path: path.runtime, reverse=True)
    runtime_by_plugins: dict[tuple[str, ...], float] = {plugins: sum(path.runtime for path in paths)
        for plugins, paths in paths_by_plugins.items()}
    total_runtime = sum(runtime_by_plugins.values())
    shards_by_plugins: dict[tuple[str, ...], list[tuple[float, list[tuple[str, str]]]]] = {}
    remaining_shards = config.shards
    for i, (plugins, _) in enumerate(paths_by_plugins.items()):
        n_shards = (remaining_shards
            if i == len(paths_by_plugins) - 1
            else 1 + round(runtime_by_plugins[plugins] / total_runtime * (config.shards - len(paths_by_plugins))))
        remaining_shards -= n_shards
        shards_by_plugins[plugins] = [(0, []) for _ in range(n_shards)]
    assert remaining_shards == 0
    for path in paths_in_runtime_order:
        shards_for_plugins = shards_by_plugins[path.plugins]
        shard_runtime, shard = shards_for_plugins[0]
        shard.append(path.path)
        heapreplace(shards_for_plugins, (shard_runtime + path.runtime, shard))
    assert shards_by_plugins.keys() == {()} | {tuple(plugins) for _, plugins in config.additional_plugins_by_prefix}
    shards = _build_shards(shards_by_plugins)
    _verify_shards(shards, testcase_variation_map, empty_testcase_paths)
    return shards


def _build_shards(shards_by_plugins: dict[tuple[str, ...], list[tuple[float, list[tuple[str, str]]]]]) -> list[Shard]:
    # Sort shards by runtime so CI nodes are more likely to pick shards with similar runtimes.
    time_ordered_shards = sorted(
        (runtime, plugin_group, paths)
        for plugin_group, runtime_paths in shards_by_plugins.items()
        for runtime, paths in runtime_paths
    )
    shards = []
    for _, plugin_group, paths in time_ordered_shards:
        shard_paths = defaultdict(list)
        for path, vid in paths:
            shard_paths[path].append(vid)
        shards.append(Shard(
            paths=shard_paths,
            plugins=frozenset(plugin_group)
        ))
    return shards


def _verify_shards(
        shards: list[Shard],
        discovered_paths_map: dict[str, list[str]],
        empty_testcase_paths: set[str],
) -> None:
    shard_paths_map = defaultdict(list)
    for shard in shards:
        for path, vids in shard.paths.items():
            shard_paths_map[path].extend(vids)
    shard_paths_set = set(shard_paths_map)
    discovered_paths_set = set(discovered_paths_map) - empty_testcase_paths  # We know empty testcases won't be in shards
    assert not shard_paths_set - discovered_paths_set,\
        f'Testcases found in shards but not in discovered set: {shard_paths_set - discovered_paths_set}'
    assert not discovered_paths_set - shard_paths_set,\
        f'Testcases found in discovered set but not in shards: {discovered_paths_set - shard_paths_set}'
    for path, vids in shard_paths_map.items():
        assert set(vids) == set(discovered_paths_map[path])
        assert sorted(vids) == sorted(discovered_paths_map[path])


def _collect_zip_test_cases(
        zip_file: zipfile.ZipFile,
        file_path: str,
        path_strs: list[str],
        expected_missing_testcases: frozenset[str],
) -> None:
    zip_files = zip_file.namelist()
    file_path_in_zip = file_path in zip_files
    if file_path in expected_missing_testcases:
        if file_path_in_zip:
            raise RuntimeError(f"Found test case file {file_path} that was expected to be missing.")
        return None
    if file_path_in_zip:
        # case insensitive search (necessary for EFM suite).
        matching_files = [
            zf for zf in zip_files
            if zf.casefold() == file_path.casefold()
        ]
        if len(matching_files) != 1:
            raise RuntimeError(f"Unable to find referenced test case file {file_path}.")
        file_path = matching_files[0]

    with zip_file.open(file_path) as fh:
        tree = etree.parse(fh)
    for test_case_index in _collect_test_case_paths(file_path, tree, path_strs):
        _collect_zip_test_cases(zip_file, test_case_index, path_strs, expected_missing_testcases)


def _collect_zip_test_case_variation_ids(zip_file: zipfile.ZipFile, test_case_paths: list[str]) -> dict[str, list[str]]:
    testcase_variation_map: dict[str, list[str]] = {}
    for test_case_path in sorted(test_case_paths):
        variation_ids: set[str] = set()
        with zip_file.open(test_case_path) as f:
            tree = etree.parse(f)
        for variation in tree.findall('{*}variation'):
            variation_id = variation.get('id')
            assert variation_id and variation_id not in variation_ids
            variation_ids.add(variation_id)
        testcase_variation_map[test_case_path] = sorted(variation_ids)
    return testcase_variation_map


def _collect_dir_test_cases(file_path_prefix: str, file_path: str, path_strs: list[str]) -> None:
    full_file_path = os.path.join(file_path_prefix, file_path)
    tree = etree.parse(full_file_path)
    for test_case_index in _collect_test_case_paths(file_path, tree, path_strs):
        _collect_dir_test_cases(file_path_prefix, test_case_index, path_strs)


def _collect_dir_test_case_variation_ids(file_path_prefix: str, test_case_paths: list[str]) -> dict[str, list[str]]:
    testcase_variation_map: dict[str, list[str]] = {}
    for test_case_path in sorted(test_case_paths):
        variation_ids: set[str] = set()
        full_path = os.path.join(file_path_prefix, test_case_path)
        tree = etree.parse(full_path)
        for variation in tree.findall('{*}variation'):
            variation_id = variation.get('id')
            assert variation_id and variation_id not in variation_ids
            variation_ids.add(variation_id)
        testcase_variation_map[test_case_path] = sorted(variation_ids)
    return testcase_variation_map


def _collect_test_case_paths(file_path: str, tree: etree._ElementTree, path_strs: list[str]) -> Generator[str, None, None]:
    testcases_elements = _get_elems_by_local_name(tree, 'testcases')
    if not testcases_elements:
        assert len(_get_elems_by_local_name(tree, 'testcase')) == 1, f'unexpected file is neither a single testcase nor index of test cases {file_path}'
        path_strs.append(file_path)
        return
    for testcases_element in testcases_elements:
        test_root = testcases_element.get('root', '')
        # replace backslashes with forward slashes, e.g. in
        # 616-definition-syntax/616-14-RXP-definition-link-validations\616-14-RXP-definition-link-validations-testcase.xml
        testcase_elements = testcases_element.findall('{*}testcase')
        for elem in testcase_elements:
            testcase_path = str(PurePosixPath(file_path).parent / test_root / cast(str, elem.get('uri')).replace('\\', '/'))
            yield testcase_path


def _get_elems_by_local_name(tree: etree._ElementTree, local_name: str) -> list[etree._Element]:
    return [tree.getroot()] if tree.getroot().tag.split('}')[-1] == local_name else tree.findall(f'{{*}}{local_name}')


def get_conformance_suite_arguments(config: ConformanceSuiteConfig, filename: str,
        additional_plugins: frozenset[str], build_cache: bool, offline: bool, log_to_file: bool,
        expected_additional_testcase_errors: dict[str, frozenset[str]],
        expected_failure_ids: frozenset[str], shard: int | None,
        testcase_filters: list[str]) -> tuple[list[Any], dict[str, Any]]:
    use_shards = shard is not None
    optional_plugins = set()
    if build_cache:
        optional_plugins.add('CacheBuilder')
    plugins = config.plugins | additional_plugins | optional_plugins
    args = [
        '--file', filename,
        '--keepOpen',
        '--testcaseResultOptions', config.test_case_result_options,
        '--validate',
    ]
    if config.package_paths:
        args.extend(['--packages', '|'.join(sorted(p.as_posix() for p in config.package_paths))])
    if plugins:
        args.extend(['--plugins', '|'.join(sorted(plugins))])
    shard_str = f'-s{shard}' if use_shards else ''
    if build_cache:
        args.extend(['--cache-builder-path', f'conf-{config.name}{shard_str}-cache.zip'])
    if config.capture_warnings:
        args.append('--testcaseResultsCaptureWarnings')
    if log_to_file:
        args.extend([
            '--csvTestReport', f'conf-{config.name}{shard_str}-report.csv',
            '--logFile', f'conf-{config.name}{shard_str}-log.txt',
        ])
    if offline or not config.network_or_cache_required:
        args.extend(['--internetConnectivity', 'offline'])
    for pattern in testcase_filters:
        args.extend(['--testcaseFilter', pattern])
    for testcase_id, errors in expected_additional_testcase_errors.items():
        args.extend(['--testcaseExpectedErrors', f'{testcase_id}|{",".join(errors)}'])
    kws = dict(
        expected_failure_ids=expected_failure_ids,
        expected_model_errors=config.expected_model_errors,
        required_locale_by_ids=config.required_locale_by_ids,
        strict_testcase_index=config.strict_testcase_index,
    )
    return args + config.args, kws


def get_conformance_suite_test_results(
        config: ConformanceSuiteConfig,
        shards: list[int],
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False,
        series: bool = False) -> list[ParameterSet]:
    assert len(shards) == 0 or config.shards != 1, \
        'Conformance suite configuration must specify shards if --shard is passed'
    if shards:
        return get_conformance_suite_test_results_with_shards(
            config=config, shards=shards, build_cache=build_cache, log_to_file=log_to_file, offline=offline, series=series
        )
    else:
        return get_conformance_suite_test_results_without_shards(
            config=config, build_cache=build_cache, log_to_file=log_to_file, offline=offline
        )


def get_conformance_suite_test_results_with_shards(
        config: ConformanceSuiteConfig,
        shards: list[int],
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False,
        series: bool = False) -> list[ParameterSet]:
    tasks = []
    all_testcase_filters = []
    for shard_id in shards:
        test_shards = get_test_shards(config)
        shard = test_shards[shard_id]
        test_paths = shard.paths
        additional_plugins = shard.plugins
        all_test_paths = {path for test_shard in test_shards for path in test_shard.paths}

        unrecognized_additional_error_ids = {_id.rsplit(':', 1)[0] for _id in config.expected_additional_testcase_errors.keys()} - all_test_paths
        assert not unrecognized_additional_error_ids, f'Unrecognized expected additional error IDs: {unrecognized_additional_error_ids}'
        expected_additional_testcase_errors = {}
        for expected_id, errors in config.expected_additional_testcase_errors.items():
            test_path, test_id = expected_id.rsplit(':', 1)
            if test_id in test_paths.get(test_path, []):
                expected_additional_testcase_errors[expected_id] = errors

        unrecognized_expected_failure_ids = {_id.rsplit(':', 1)[0] for _id in config.expected_failure_ids} - all_test_paths
        assert not unrecognized_expected_failure_ids, f'Unrecognized expected failure IDs: {unrecognized_expected_failure_ids}'
        expected_failure_ids = set()
        for expected_failure_id in config.expected_failure_ids:
            test_path, test_id = expected_failure_id.rsplit(':', 1)
            if test_id in test_paths.get(test_path, []):
                expected_failure_ids.add(expected_failure_id)

        testcase_filters = sorted([
            f'*{os.path.sep}{path}:{vid}'
            for path, vids in test_paths.items()
            for vid in vids
        ])
        all_testcase_filters.extend(testcase_filters)
        filename = config.entry_point_path.as_posix()
        args = get_conformance_suite_arguments(
            config=config, filename=filename, additional_plugins=additional_plugins,
            build_cache=build_cache, offline=offline, log_to_file=log_to_file, shard=shard_id,
            expected_additional_testcase_errors=expected_additional_testcase_errors,
            expected_failure_ids=frozenset(expected_failure_ids), testcase_filters=testcase_filters,
        )
        tasks.append(args)
    url_context_manager: ContextManager[Any]
    if config.url_replace:
        url_context_manager = patch('arelle.WebCache.WebCache.normalizeUrl', normalize_url_function(config))
    else:
        url_context_manager = nullcontext()
    if series:
        with url_context_manager:
            results = []
            for args in tasks:
                task_results = get_test_data_mp_wrapper(args)
                results.extend(task_results)
    else:
        with url_context_manager, multiprocessing.Pool() as pool:
            parallel_results = pool.map(get_test_data_mp_wrapper, tasks)
            results = [x for l in parallel_results for x in l]
    assert len(results) == len(all_testcase_filters),\
        f'Expected {len(all_testcase_filters)} results based on testcase filters, received {len(results)}'
    return results


def get_conformance_suite_test_results_without_shards(
        config: ConformanceSuiteConfig,
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False) -> list[ParameterSet]:
    additional_plugins = frozenset().union(*(plugins for _, plugins in config.additional_plugins_by_prefix))
    filename = config.entry_point_path.as_posix()
    expected_failure_ids = config.expected_failure_ids
    args, kws = get_conformance_suite_arguments(
        config=config, filename=filename, additional_plugins=additional_plugins,
        build_cache=build_cache, offline=offline, log_to_file=log_to_file, shard=None,
        expected_additional_testcase_errors=config.expected_additional_testcase_errors,
        expected_failure_ids=expected_failure_ids, testcase_filters=[],
    )
    url_context_manager: ContextManager[Any]
    if config.url_replace:
        url_context_manager = patch('arelle.WebCache.WebCache.normalizeUrl', normalize_url_function(config))
    else:
        url_context_manager = nullcontext()
    with url_context_manager:
        return get_test_data(args, **kws)


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
        actual_codes = result.values[0].get('actual')  # type: ignore[union-attr]
        for code in actual_codes:
            rows.append((testcase_id, code))
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
        values = result.values[0]
        # TODO: revisit typing here once 3.8 removed
        status = values.get('status')  # type: ignore[union-attr]
        assert status, f'Test result has no status: {testcase_id}'
        if status == 'skip':
            continue
        assert testcase_id and testcase_id not in durations
        duration = values.get('duration')  # type: ignore[union-attr]
        if duration:
            durations[testcase_id] = duration
    if durations:
        duration_values = durations.values()
        duration_mean = statistics.mean(duration_values)
        duration_stdev = statistics.stdev(duration_values)
        durations = {
            testcase_id: duration/duration_mean
            for testcase_id, duration in sorted(durations.items())
        }
        durations['<mean>'] = duration_mean
        durations['<stdev>'] = duration_stdev
    with open(f'conf-{config.name}-timing.json', 'w') as file:
        json.dump(durations, file, indent=4)
