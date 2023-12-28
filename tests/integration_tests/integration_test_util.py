from __future__ import annotations

import os.path
from collections import Counter
from pathlib import PurePath
from typing import TYPE_CHECKING, cast

import pytest

from arelle import ModelDocument, PackageManager, PluginManager
from arelle.CntlrCmdLine import parseAndRun
from arelle.FileSource import archiveFilenameParts

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


def get_document_id(doc: ModelDocument.ModelDocument) -> str:
    file_source = doc.modelXbrl.fileSource
    basepath = getattr(file_source, 'basefile', None)
    if basepath is None:
        # Try and find a basepath from referenced documents
        ref_file_source = next(iter(file_source.referencedFileSources.values()), None)
        if ref_file_source is not None:
            basepath = ref_file_source.basefile
    if basepath is None:
        # Try and find a basepath based on archive in path
        archivePathParts = archiveFilenameParts(doc.filepath)
        if archivePathParts is not None:
            return archivePathParts[1]
    if basepath is None:
        # Use file source URL as fallback if basepath not found
        basepath = os.path.dirname(file_source.url) + os.sep
    return PurePath(doc.filepath).relative_to(basepath).as_posix()


def get_test_data(
        args: list[str],
        expected_failure_ids: frozenset[str] = frozenset(),
        expected_empty_testcases: frozenset[str] = frozenset(),
        expected_model_errors: frozenset[str] = frozenset(),
        strict_testcase_index: bool = True,
) -> list[ParameterSet]:
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :param expected_empty_testcases: The set of paths of empty testcases, relative to the suite zip
    :param expected_model_errors: The set of error codes expected to be in the ModelXbrl errors
    :param strict_testcase_index: Don't allow IOerrors when loading the testcase index
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
            if strict_testcase_index:
                model_errors = sorted(cntlr.modelManager.modelXbrl.errors)
                assert 'IOerror' not in model_errors, f'One or more testcases referenced by testcases index "{model_document.filepath}" were not found.'
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
