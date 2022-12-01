from __future__ import annotations
import os.path
import pytest
from collections import Counter
from contextlib import nullcontext
from pathlib import PurePath
from typing import Callable
from unittest.mock import patch

from arelle import ModelDocument, PackageManager, PluginManager
from arelle.CntlrCmdLine import parseAndRun
from arelle.WebCache import WebCache

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig


def _get_path_tail(uri: str) -> tuple[str]:
    path = PurePath(uri)
    return path.parts[-3:-1] if path.name == 'index.xml' else path.parts[-2:]


def get_test_data(
        args: list[str],
        expected_failure_ids: frozenset[str] = frozenset(),
        expected_empty_testcases: frozenset[str] = frozenset(),
        expected_model_errors: frozenset[str] = frozenset()) -> list[pytest.param]:
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :param expected_empty_testcases: The set of paths of empty testcases, relative to the suite zip
    :param expected_model_errors: The set of error codes expected to be in the ModelXbrl errors
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    """
    cntlr = parseAndRun(args)
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
            test_case_path_tail = _get_path_tail(model_document.uri)
            test_id = '/'.join(test_case_path_tail)
            model_errors = sorted(cntlr.modelManager.modelXbrl.errors)
            expected_model_errors = sorted(expected_model_errors)
            param = pytest.param(
                {
                    'status': 'pass' if model_errors == expected_model_errors else 'fail',
                    'expected': expected_model_errors,
                    'actual': model_errors
                },
                id=test_id,
                marks=[pytest.mark.xfail()] if test_id in expected_failure_ids else []
            )
            results.append(param)
        else:
            raise Exception('Unhandled model document type: {}'.format(model_document.type))
        for test_case in test_cases:
            test_case_path_tail = _get_path_tail(test_case.uri)
            if test_case.type not in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
                test_cases_with_unrecognized_type[test_case_path_tail] = test_case.type
            if not getattr(test_case, "testcaseVariations", None) and \
                    os.path.relpath(test_case.filepath, model_document.modelXbrl.fileSource.basefile) not in expected_empty_testcases:
                test_cases_with_no_variations.add(test_case_path_tail)
            else:
                for mv in test_case.testcaseVariations:
                    test_id = '{}/{}'.format('/'.join(test_case_path_tail), mv.id)
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
        if test_cases_with_no_variations:
            raise Exception(f"Some test cases don't have any variations: {sorted(test_cases_with_no_variations)}.")
        test_id_frequencies = Counter(p.id for p in results)
        nonunique_test_ids = {test_id: count for test_id, count in test_id_frequencies.items() if count > 1}
        if nonunique_test_ids:
            raise Exception(f'Some test IDs are not unique.  Frequencies of nonunique test IDs: {nonunique_test_ids}.')
        nonexistent_expected_failure_ids = expected_failure_ids - set(test_id_frequencies)
        if nonexistent_expected_failure_ids:
            raise Exception(f"Some expected failure IDs don't match any test cases: {sorted(nonexistent_expected_failure_ids)}.")
        return results
    finally:
        cntlr.modelManager.close()
        PackageManager.close()
        PluginManager.close()


original_normalize_url_function = WebCache.normalizeUrl


def normalize_url_function(config: ConformanceSuiteConfig) -> Callable:
    def normalize_url(self, url, base=None):
        if url.startswith(config.url_replace):
            return url.replace(config.url_replace, f'{config.prefixed_local_filepath}/')
        return original_normalize_url_function(self, url, base)
    return normalize_url


def get_conformance_suite_test_results(
        config: ConformanceSuiteConfig,
        log_to_file: bool = False,
        offline: bool = False) -> list[pytest.param]:
    args = [
        '--file', os.path.join(config.prefixed_local_filepath, config.file),
        '--keepOpen',
        '--validate',
    ]
    if config.capture_warnings:
        args.append('--testcaseResultsCaptureWarnings')
    if log_to_file:
        args.extend([
            '--csvTestReport', f'conf-{config.name}-report.csv',
            '--logFile', f'conf-{config.name}-log.txt',
        ])
    if offline:
        args.extend(['--internetConnectivity', 'offline'])
    if config.url_replace:
        context_manager = patch('arelle.WebCache.WebCache.normalizeUrl', normalize_url_function(config))
    else:
        context_manager = nullcontext()
    with context_manager:
        return get_test_data(
            args + config.args,
            expected_failure_ids=config.expected_failure_ids,
            expected_empty_testcases=config.expected_empty_testcases,
            expected_model_errors=config.expected_model_errors
        )
