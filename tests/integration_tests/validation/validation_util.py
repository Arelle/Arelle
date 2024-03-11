from __future__ import annotations

import json
import multiprocessing
import os.path
import statistics
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Generator
from contextlib import ExitStack
from contextlib import nullcontext
from dataclasses import dataclass
from heapq import heapreplace
from pathlib import PurePath, PurePosixPath, Path
from typing import Any, Callable, ContextManager, TYPE_CHECKING, cast
from unittest.mock import patch

from lxml import etree

from arelle.WebCache import WebCache
from tests.integration_tests.integration_test_util import get_test_data
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


original_normalize_url_function = WebCache.normalizeUrl
CONFORMANCE_SUITE_TIMING_PATH_PREFIX = 'tests/resources/conformance_suites_timing'


def normalize_url_function(config: ConformanceSuiteConfig) -> Callable[[WebCache, str, str | None], str]:
    def normalize_url(self: WebCache, url: str, base: str | None = None) -> str:
        assert config.url_replace is not None
        if url.startswith(config.url_replace):
            return url.replace(config.url_replace, f'{config.prefixed_final_filepath}/')
        return cast(str, original_normalize_url_function(self, url, base))
    return normalize_url


def get_test_data_mp_wrapper(args_kws: tuple[list[Any], dict[str, Any]]) -> list[ParameterSet]:
    args, kws = args_kws
    return get_test_data(args, **kws)


def get_test_shards(config: ConformanceSuiteConfig) -> list[tuple[list[str], frozenset[str]]]:
    path_strs: list[str] = []
    final_filepath = config.prefixed_final_filepath
    if zipfile.is_zipfile(final_filepath):
        with zipfile.ZipFile(final_filepath) as zip_file:
            _collect_zip_test_cases(zip_file, config.file, path_strs)
    else:
        _collect_dir_test_cases(final_filepath, config.file, path_strs)
    path_strs = sorted(path_strs)
    assert path_strs

    @dataclass(frozen=True)
    class PathInfo:
        path: str
        plugins: tuple[str, ...]
        runtime: float
    paths_by_plugins: dict[tuple[str, ...], list[PathInfo]] = defaultdict(list)
    approximate_relative_timing = config.approximate_relative_timing
    if approximate_relative_timing is None:
        approximate_relative_timing = load_timing_file(config.name)
    for path_str in path_strs:
        path_plugins: set[str] = set()
        for prefix, additional_plugins in config.additional_plugins_by_prefix:
            if path_str.startswith(prefix):
                path_plugins.update(additional_plugins)
        paths_by_plugins[tuple(path_plugins)].append(
            PathInfo(path=path_str, plugins=tuple(path_plugins), runtime=approximate_relative_timing.get(path_str, 1)))
    paths_in_runtime_order: list[PathInfo] = sorted((path for paths in paths_by_plugins.values() for path in paths),
        key=lambda path: path.runtime, reverse=True)
    runtime_by_plugins: dict[tuple[str, ...], float] = {plugins: sum(path.runtime for path in paths)
        for plugins, paths in paths_by_plugins.items()}
    total_runtime = sum(runtime_by_plugins.values())
    shards_by_plugins: dict[tuple[str, ...], list[tuple[float, list[str]]]] = {}
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
    # Sort shards by runtime so CI nodes are more likely to pick shards with similar runtimes.
    time_ordered_shards = sorted(
        (runtime, plugin_group, paths)
        for plugin_group, runtime_paths in shards_by_plugins.items()
        for runtime, paths in runtime_paths
    )
    shards = [
        (paths, frozenset(plugin_group))
        for _, plugin_group, paths in time_ordered_shards
    ]
    assert sorted(path for paths, _ in shards for path in paths) == path_strs
    return shards


def _collect_zip_test_cases(zip_file: zipfile.ZipFile, file_path: str, path_strs: list[str]) -> None:
    zip_files = zip_file.namelist()
    if file_path not in zip_files:
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
        _collect_zip_test_cases(zip_file, test_case_index, path_strs)


def _collect_dir_test_cases(file_path_prefix: str, file_path: str, path_strs: list[str]) -> None:
    full_file_path = os.path.join(file_path_prefix, file_path)
    tree = etree.parse(full_file_path)
    for test_case_index in _collect_test_case_paths(file_path, tree, path_strs):
        _collect_dir_test_cases(file_path_prefix, test_case_index, path_strs)


def _collect_test_case_paths(file_path: str, tree: etree._ElementTree, path_strs: list[str]) -> Generator[str, None, None]:
    testcases_element = _get_elem_by_local_name(tree, 'testcases')
    if testcases_element is not None:
        test_root = testcases_element.get('root', '')
        # replace backslashes with forward slashes, e.g. in
        # 616-definition-syntax/616-14-RXP-definition-link-validations\616-14-RXP-definition-link-validations-testcase.xml
        for elem in testcases_element.findall('{*}testcase'):
            yield str(PurePosixPath(file_path).parent / test_root / cast(str, elem.get('uri')).replace('\\', '/'))
    else:
        assert _get_elem_by_local_name(tree, 'testcase') is not None, f'unexpected file is neither test case nor index of test cases {file_path}'
        path_strs.append(file_path)


def _get_elem_by_local_name(tree: etree._ElementTree, local_name: str) -> etree._Element | None:
    return tree.getroot() if tree.getroot().tag.split('}')[-1] == local_name else tree.find(f'{{*}}{local_name}')


def get_conformance_suite_arguments(config: ConformanceSuiteConfig, filename: str,
        additional_plugins: frozenset[str], build_cache: bool, offline: bool, log_to_file: bool,
        expected_failure_ids: frozenset[str], expected_empty_testcases: frozenset[str],
        shard: int | None) -> tuple[list[Any], dict[str, Any]]:
    use_shards = shard is not None
    optional_plugins = set()
    if build_cache:
        optional_plugins.add('CacheBuilder')
    plugins = config.plugins | additional_plugins | optional_plugins
    args = [
        '--file', filename,
        '--keepOpen',
        '--validate',
    ]
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
    kws = dict(
        expected_failure_ids=expected_failure_ids,
        expected_empty_testcases=expected_empty_testcases,
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


def get_conformance_suite_test_results_with_shards(  # type: ignore[return]
        config: ConformanceSuiteConfig,
        shards: list[int],
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False,
        series: bool = False) -> list[ParameterSet]:
    tempfiles: list[Any] = []
    try:
        with ExitStack() as exit_stack:
            # delete=False and subsequent .close and unlink are for Windows compatibility.  bpo-14243
            tempfiles.extend(exit_stack.enter_context(tempfile.NamedTemporaryFile(dir='.', mode='wb', suffix='.xml', delete=False)) for _ in shards)
            tasks = []
            for shard, testcase_file in zip(shards, tempfiles):
                test_shards = get_test_shards(config)
                test_paths, additional_plugins = test_shards[shard]
                zip_path = config.prefixed_final_filepath
                all_test_paths = {path for test_paths, _ in test_shards for path in test_paths}
                unrecognized_expected_empty_testcases = config.expected_empty_testcases - all_test_paths
                assert not unrecognized_expected_empty_testcases, f'Unrecognized expected empty testcases: {unrecognized_expected_empty_testcases}'
                expected_empty_testcases = config.expected_empty_testcases.intersection(test_paths)
                unrecognized_expected_failure_ids = {id.rsplit(':', 1)[0] for id in config.expected_failure_ids} - all_test_paths
                assert not unrecognized_expected_failure_ids, f'Unrecognized expected failure IDs: {unrecognized_expected_failure_ids}'
                expected_failure_ids = frozenset(id for id in config.expected_failure_ids if id.rsplit(':', 1)[0] in test_paths)

                root = etree.Element('testcases')
                tree = etree.ElementTree(root)
                pathlib_zip_path = PurePath(zip_path)
                for test_path in test_paths:
                    etree.SubElement(root, 'testcase', uri=str((pathlib_zip_path / test_path).as_posix()))
                tree.write(testcase_file, encoding='utf-8', pretty_print=True, xml_declaration=True)
                testcase_file.flush()
                testcase_file.close()
                filename = testcase_file.name
                args = get_conformance_suite_arguments(
                    config=config, filename=filename, additional_plugins=additional_plugins,
                    build_cache=build_cache, offline=offline, log_to_file=log_to_file, shard=shard,
                    expected_failure_ids=expected_failure_ids, expected_empty_testcases=expected_empty_testcases,
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
                    return results
            else:
                with url_context_manager, multiprocessing.Pool() as pool:
                    parallel_results = pool.map(get_test_data_mp_wrapper, tasks)
                    return [x for l in parallel_results for x in l]
    finally:
        for f in tempfiles:
            try:
                os.unlink(f.name)
            except OSError:
                pass


def get_conformance_suite_test_results_without_shards(
        config: ConformanceSuiteConfig,
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False) -> list[ParameterSet]:
    additional_plugins = frozenset().union(*(plugins for _, plugins in config.additional_plugins_by_prefix))
    filename = os.path.join(config.prefixed_final_filepath, config.file)
    expected_empty_testcases = config.expected_empty_testcases
    expected_failure_ids = config.expected_failure_ids
    args, kws = get_conformance_suite_arguments(
        config=config, filename=filename, additional_plugins=additional_plugins,
        build_cache=build_cache, offline=offline, log_to_file=log_to_file, shard=None,
        expected_failure_ids=expected_failure_ids, expected_empty_testcases=expected_empty_testcases,
    )
    url_context_manager: ContextManager[Any]
    if config.url_replace:
        url_context_manager = patch('arelle.WebCache.WebCache.normalizeUrl', normalize_url_function(config))
    else:
        url_context_manager = nullcontext()
    with url_context_manager:
        return get_test_data(args, **kws)


def load_timing_file(name: str) -> dict[str, float]:
    path = Path(CONFORMANCE_SUITE_TIMING_PATH_PREFIX) / Path(name).with_suffix(".json")
    if not path.exists():
        return {}
    with open(path) as file:
        data = json.load(file)
        return {
            str(k): float(v)
            for k, v in data.items()
        }


def save_timing_file(config: ConformanceSuiteConfig, results: list[ParameterSet]) -> None:
    timing: dict[str, float] = defaultdict(float)
    for result in results:
        assert result.id
        testcase_id = result.id.rsplit(':', 1)[0]
        values = result.values[0]
        # TODO: revisit typing here once 3.8 removed
        duration = values.get('duration')  # type: ignore[union-attr]
        if duration:
            timing[testcase_id] += duration
    if timing:
        duration_avg = statistics.mean(timing.values())
        timing = {
            testcase_id: duration/duration_avg
            for testcase_id, duration in sorted(timing.items())
        }
    with open(f'conf-{config.name}-timing.json', 'w') as file:
        json.dump(timing, file, indent=4)
