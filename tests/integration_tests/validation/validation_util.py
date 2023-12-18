from __future__ import annotations

import os.path
import tempfile
from collections import defaultdict
from contextlib import nullcontext
from dataclasses import dataclass
from heapq import heapreplace
from pathlib import PurePath, PurePosixPath
from typing import Any, Callable, ContextManager, TYPE_CHECKING, cast
from unittest.mock import patch
from zipfile import ZipFile

from lxml import etree

from arelle.WebCache import WebCache
from tests.integration_tests.integration_test_util import get_test_data
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


original_normalize_url_function = WebCache.normalizeUrl


def normalize_url_function(config: ConformanceSuiteConfig) -> Callable[[WebCache, str, str | None], str]:
    def normalize_url(self: WebCache, url: str, base: str | None = None) -> str:
        assert config.url_replace is not None
        if url.startswith(config.url_replace):
            return url.replace(config.url_replace, f'{config.prefixed_local_filepath}/')
        return cast(str, original_normalize_url_function(self, url, base))
    return normalize_url


def get_test_shards(config: ConformanceSuiteConfig) -> list[tuple[list[str], frozenset[str]]]:
    test_path_prefix = PurePosixPath(config.file).parent
    with ZipFile(config.prefixed_local_filepath) as zip_file:
        tree = etree.parse(zip_file.open(config.file))
        testcases_element = tree.getroot() if tree.getroot().tag == 'testcases' else tree.find('testcases')
        assert testcases_element is not None
        test_root = testcases_element.get('root', '')
        # replace backslashes with forward slashes, e.g. in
        # 616-definition-syntax/616-14-RXP-definition-link-validations\616-14-RXP-definition-link-validations-testcase.xml
        path_strs = sorted(str(test_path_prefix / test_root / cast(str, e.get('uri')).replace('\\', '/'))
            for e in testcases_element.findall('testcase'))
    assert path_strs

    @dataclass(frozen=True)
    class Path:
        path: str
        plugins: tuple[str, ...]
        runtime: float
    paths_by_plugins: dict[tuple[str, ...], list[Path]] = defaultdict(list)
    for path_str in path_strs:
        path_plugins: set[str] = set()
        for prefix, additional_plugins in config.additional_plugins_by_prefix:
            if path_str.startswith(prefix):
                path_plugins.update(additional_plugins)
        paths_by_plugins[tuple(path_plugins)].append(
            Path(path=path_str, plugins=tuple(path_plugins), runtime=config.approximate_relative_timing.get(path_str, 1)))
    paths_in_runtime_order: list[Path] = sorted((path for paths in paths_by_plugins.values() for path in paths),
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
    shards = [(paths, frozenset(plugins))
        for plugins, runtimes_paths in shards_by_plugins.items()
        for _, paths in runtimes_paths]
    assert sorted(path for paths, _ in shards for path in paths) == path_strs
    return shards


def get_conformance_suite_test_results(
        config: ConformanceSuiteConfig,
        shard: int | None,
        build_cache: bool = False,
        log_to_file: bool = False,
        offline: bool = False) -> list[ParameterSet]:
    file_path = os.path.join(config.prefixed_local_filepath, config.file)
    assert shard is None or config.shards != 1, \
        'Conformance suite configuration must specify shards if --shard is passed'
    use_shards = shard is not None
    testcase_file_cm: Callable[[], ContextManager[Any]] = \
        (lambda: tempfile.NamedTemporaryFile(dir='.', mode='wb', suffix='.xml')) if use_shards else nullcontext  # type: ignore[assignment]
    with testcase_file_cm() as testcase_file:
        if use_shards:
            assert shard is not None
            shards = get_test_shards(config)
            test_paths, additional_plugins = shards[shard]
            zip_path = config.prefixed_local_filepath
            all_test_paths = {path for test_paths, _ in shards for path in test_paths}
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
            filename = testcase_file.name
        else:
            additional_plugins = frozenset().union(*(plugins for _, plugins in config.additional_plugins_by_prefix))
            filename = file_path
            expected_empty_testcases = config.expected_empty_testcases
            expected_failure_ids = config.expected_failure_ids
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
        context_manager: ContextManager[Any]
        if config.url_replace:
            context_manager = patch('arelle.WebCache.WebCache.normalizeUrl', normalize_url_function(config))
        else:
            context_manager = nullcontext()
        with context_manager:
            return get_test_data(
                args + config.args,
                expected_failure_ids=expected_failure_ids,
                expected_empty_testcases=expected_empty_testcases,
                expected_model_errors=config.expected_model_errors,
                strict_testcase_index=config.strict_testcase_index,
            )
