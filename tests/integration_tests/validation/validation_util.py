from __future__ import annotations
import os.path
import pytest
import tempfile
from collections import Counter, defaultdict
from contextlib import nullcontext
from dataclasses import dataclass
from heapq import heapreplace
from lxml import etree
from pathlib import PurePath, PurePosixPath
from typing import Any, Callable, ContextManager, TYPE_CHECKING, cast
from unittest.mock import patch
from zipfile import ZipFile

from arelle import ModelDocument, PackageManager, PluginManager
from arelle.CntlrCmdLine import parseAndRun
from arelle.FileSource import archiveFilenameParts
from arelle.WebCache import WebCache

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


def get_document_id(doc: ModelDocument.ModelDocument) -> str:
    file_source = doc.modelXbrl.fileSource
    basefile = getattr(file_source, 'basefile', None)
    if basefile is None:
        file_source = next(iter(file_source.referencedFileSources.values()), None)
        if file_source is not None:
            basefile = file_source.basefile
    if basefile is not None:
        doc_id = PurePath(doc.filepath).relative_to(basefile).as_posix()
    else:
        # give up
        parts = archiveFilenameParts(doc.filepath)
        assert parts is not None
        _, doc_id = parts
    return doc_id


def get_test_data(
        args: list[str],
        expected_failure_ids: frozenset[str] = frozenset(),
        expected_empty_testcases: frozenset[str] = frozenset(),
        expected_model_errors: frozenset[str] = frozenset()) -> list[ParameterSet]:
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :param expected_empty_testcases: The set of paths of empty testcases, relative to the suite zip
    :param expected_model_errors: The set of error codes expected to be in the ModelXbrl errors
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    """
    cntlr = parseAndRun(args)  # type: ignore[no-untyped-call]
    try:
        results = []
        test_cases_with_no_variations = set()
        test_cases_with_unrecognized_type = {}
        model_document = cntlr.modelManager.modelXbrl.modelDocument
        test_cases: list[ModelDocument.ModelDocument] = []
        if model_document.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
            test_cases.append(model_document)
        elif model_document.type == ModelDocument.Type.TESTCASESINDEX:
            referenced_documents = model_document.referencesDocument.keys()
            child_document_types = {doc.type for doc in referenced_documents}
            assert len(child_document_types) == 1, f'Multiple child document types found in {model_document.uri}: {child_document_types}.'
            [child_document_type] = child_document_types
            # the formula function registry conformance suite points to a list of registries, so we need to search one level deeper.
            if child_document_type == ModelDocument.Type.REGISTRY:
                referenced_documents = [case for doc in referenced_documents for case in doc.referencesDocument.keys()]
            test_cases = sorted(referenced_documents, key=lambda doc: doc.uri)
        elif model_document.type == ModelDocument.Type.INSTANCE:
            test_id = get_document_id(model_document)
            model_errors = sorted(cntlr.modelManager.modelXbrl.errors)
            expected_model_errors_list = sorted(expected_model_errors)
            param = pytest.param(
                {
                    'status': 'pass' if model_errors == expected_model_errors_list else 'fail',
                    'expected': expected_model_errors_list,
                    'actual': model_errors
                },
                id=test_id,
                marks=[pytest.mark.xfail()] if test_id in expected_failure_ids else []
            )
            results.append(param)
        else:
            raise Exception('Unhandled model document type: {}'.format(model_document.type))
        for test_case in test_cases:
            test_case_file_id = get_document_id(test_case)
            if test_case.type not in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
                test_cases_with_unrecognized_type[test_case_file_id] = test_case.type
            if not getattr(test_case, "testcaseVariations", None):
                test_cases_with_no_variations.add(test_case_file_id)
            else:
                for mv in test_case.testcaseVariations:
                    test_id = f'{test_case_file_id}:{mv.id}'
                    param = pytest.param(
                        {
                            'status': mv.status,
                            'expected': mv.expected,
                            'actual': mv.actual
                        },
                        id=test_id,
                        marks=[pytest.mark.xfail()] if test_id in expected_failure_ids else []
                    )
                    results.append(param)
        if test_cases_with_unrecognized_type:
            raise Exception(f"Some test cases have an unrecognized document type: {sorted(test_cases_with_unrecognized_type.items())}.")
        unrecognized_expected_empty_testcases = expected_empty_testcases.difference(map(get_document_id, test_cases))
        if unrecognized_expected_empty_testcases:
            raise Exception(f"Some expected empty test cases weren't found: {sorted(unrecognized_expected_empty_testcases)}.")
        unexpected_empty_testcases = test_cases_with_no_variations - expected_empty_testcases
        if unexpected_empty_testcases:
            raise Exception(f"Some test cases don't have any variations: {sorted(unexpected_empty_testcases)}.")
        test_id_frequencies = Counter(cast(str, p.id) for p in results)
        nonunique_test_ids = {test_id: count for test_id, count in test_id_frequencies.items() if count > 1}
        if nonunique_test_ids:
            raise Exception(f'Some test IDs are not unique.  Frequencies of nonunique test IDs: {nonunique_test_ids}.')
        nonexistent_expected_failure_ids = expected_failure_ids - test_id_frequencies.keys()
        if nonexistent_expected_failure_ids:
            raise Exception(f"Some expected failure IDs don't match any test cases: {sorted(nonexistent_expected_failure_ids)}.")
        return results
    finally:
        cntlr.modelManager.close()
        PackageManager.close()  # type: ignore[no-untyped-call]
        PluginManager.close()  # type: ignore[no-untyped-call]


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
        plugins = config.plugins | additional_plugins
        args = [
            '--file', filename,
            '--keepOpen',
            '--validate',
        ]
        if plugins:
            args.extend(['--plugins', '|'.join(sorted(plugins))])
        if config.capture_warnings:
            args.append('--testcaseResultsCaptureWarnings')
        if log_to_file:
            shard_str = f'-s{shard}' if use_shards else ''
            args.extend([
                '--csvTestReport', f'conf-{config.name}{shard_str}-report.csv',
                '--logFile', f'conf-{config.name}{shard_str}-log.txt',
            ])
        if offline:
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
                expected_model_errors=config.expected_model_errors
            )
