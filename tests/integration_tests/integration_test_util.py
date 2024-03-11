from __future__ import annotations

import locale
import os.path
import re
from collections import Counter
from pathlib import PurePath
from typing import TYPE_CHECKING, cast

import pytest

from arelle import ModelDocument, PackageManager, PluginManager
from arelle.Cntlr import Cntlr
from arelle.CntlrCmdLine import parseAndRun
from arelle.FileSource import archiveFilenameParts

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


def get_document_id(doc: ModelDocument.ModelDocument) -> str:
    """
    Given a ModelDocument, attempt to find a basepath that can be used to generate a user-friendly document ID
    :param doc:
    :return: A parent path of the document's filepath.
    """
    parents = [p.as_posix() for p in PurePath(doc.filepath).parents]
    checked_paths = set()
    file_source = doc.modelXbrl.fileSource
    # Try basefile
    basefile: str = cast(str, getattr(file_source, 'basefile', None))
    if basefile is not None:
        basefile = PurePath(basefile).as_posix()
        if basefile in parents:
            return get_document_id_from_basepath(doc, basefile)
        else:
            checked_paths.add(basefile)
    # Try referenced documents
    ref_file_source = next(iter(file_source.referencedFileSources.values()), None)
    ref_basefile: str = ref_file_source.basefile if ref_file_source is not None else None
    if ref_basefile is not None:
        ref_basefile = PurePath(ref_basefile).as_posix()
        if ref_basefile in parents:
            return get_document_id_from_basepath(doc, ref_basefile)
        else:
            checked_paths.add(ref_basefile)
    # Try archive subpath
    archive_path_parts = archiveFilenameParts(doc.filepath)
    if archive_path_parts is not None:
        archive_path_part = PurePath(archive_path_parts[1]).as_posix()
        return archive_path_part
    # Use file source URL as fallback if basepath not found
    file_source_url = PurePath(os.path.dirname(file_source.url)).as_posix()
    if file_source_url in parents:
        return get_document_id_from_basepath(doc, file_source_url)
    else:
        checked_paths.add(file_source_url)
    raise ValueError(f'Could not determine basepath. '
                     f'None of the checked paths ({checked_paths}) were parents of \"{doc.filepath}\".')


def get_document_id_from_basepath(doc: ModelDocument.ModelDocument, basepath: str) -> str:
    return PurePath(doc.filepath).relative_to(basepath).as_posix()


def get_s3_uri(path: str, version_id: str | None = None) -> str:
    uri = f'https://arelle-public.s3.amazonaws.com/{path}'
    if version_id is not None:
        uri += f'?versionId={version_id}'
    return uri


def get_test_data(
        args: list[str],
        expected_failure_ids: frozenset[str] = frozenset(),
        expected_empty_testcases: frozenset[str] = frozenset(),
        expected_model_errors: frozenset[str] = frozenset(),
        required_locale_by_ids: dict[str, re.Pattern[str]] | None = None,
        strict_testcase_index: bool = True,
) -> list[ParameterSet]:
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :param expected_empty_testcases: The set of paths of empty testcases, relative to the suite zip
    :param expected_model_errors: The set of error codes expected to be in the ModelXbrl errors
    :param required_locale_by_ids: The dict of IDs for tests which require a system locale matching a regex pattern.
    :param strict_testcase_index: Don't allow IOerrors when loading the testcase index
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    """
    if required_locale_by_ids is None:
        required_locale_by_ids = {}
    cntlr = parseAndRun(args)  # type: ignore[no-untyped-call]
    try:
        system_locale = locale.setlocale(locale.LC_CTYPE)
        results: list[ParameterSet] = []
        test_cases_with_no_variations = set()
        test_cases_with_unrecognized_type = {}
        model_document = cntlr.modelManager.modelXbrl.modelDocument
        test_cases: list[ModelDocument.ModelDocument] = []
        if strict_testcase_index and model_document.type == ModelDocument.Type.TESTCASESINDEX:
            model_errors = sorted(cntlr.modelManager.modelXbrl.errors)
            assert 'IOerror' not in model_errors, f'One or more testcases referenced by testcases index "{model_document.filepath}" were not found.'
        collect_test_data(
            cntlr=cntlr,
            expected_failure_ids=expected_failure_ids,
            expected_empty_testcases=expected_empty_testcases,
            expected_model_errors=expected_model_errors,
            required_locale_by_ids=required_locale_by_ids,
            system_locale=system_locale,
            results=results,
            model_document=model_document,
            test_cases=test_cases,
        )
        for test_case in sorted(test_cases, key=lambda doc: doc.uri):
            test_case_file_id = get_document_id(test_case)
            if test_case.type not in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
                test_cases_with_unrecognized_type[test_case_file_id] = test_case.type
            if not getattr(test_case, "testcaseVariations", None):
                test_cases_with_no_variations.add(test_case_file_id)
            else:
                for mv in test_case.testcaseVariations:
                    test_id = f'{test_case_file_id}:{mv.id}'
                    expected_failure = isExpectedFailure(test_id, expected_failure_ids, required_locale_by_ids, system_locale)
                    param = pytest.param(
                        {
                            'status': mv.status,
                            'expected': mv.expected,
                            'actual': mv.actual,
                            'duration': mv.duration,
                        },
                        id=test_id,
                        marks=[pytest.mark.xfail()] if expected_failure else [],
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
        unexpected_nonempty_testcases = expected_empty_testcases - test_cases_with_no_variations
        if unexpected_nonempty_testcases:
            raise Exception(f"Some test cases with variations were expected to be empty: {sorted(unexpected_nonempty_testcases)}.")
        test_id_frequencies = Counter(cast(str, p.id) for p in results)
        nonunique_test_ids = {test_id: count for test_id, count in test_id_frequencies.items() if count > 1}
        if nonunique_test_ids:
            raise Exception(f'Some test IDs are not unique.  Frequencies of nonunique test IDs: {nonunique_test_ids}.')
        nonexistent_expected_failure_ids = expected_failure_ids - test_id_frequencies.keys()
        if nonexistent_expected_failure_ids:
            raise Exception(f"Some expected failure IDs don't match any test cases: {sorted(nonexistent_expected_failure_ids)}.")
        nonexistent_required_locale_testcase_ids = required_locale_by_ids.keys() - test_id_frequencies.keys()
        if nonexistent_required_locale_testcase_ids:
            raise Exception(f"Some required locale IDs don't match any test cases: {sorted(nonexistent_required_locale_testcase_ids)}.")
        return results
    finally:
        cntlr.modelManager.close()
        PackageManager.close()  # type: ignore[no-untyped-call]
        PluginManager.close()  # type: ignore[no-untyped-call]


def collect_test_data(
        cntlr: Cntlr,
        expected_failure_ids: frozenset[str],
        expected_empty_testcases: frozenset[str],
        expected_model_errors: frozenset[str],
        required_locale_by_ids: dict[str, re.Pattern[str]],
        system_locale: str,
        results: list[ParameterSet],
        model_document: ModelDocument.ModelDocument,
        test_cases: list[ModelDocument.ModelDocument],
) -> None:
    if model_document.type == ModelDocument.Type.TESTCASESINDEX:
        for child_document in model_document.referencesDocument.keys():
            collect_test_data(
                cntlr=cntlr,
                expected_failure_ids=expected_failure_ids,
                expected_empty_testcases=expected_empty_testcases,
                expected_model_errors=expected_model_errors,
                required_locale_by_ids=required_locale_by_ids,
                system_locale=system_locale,
                results=results,
                model_document=child_document,
                test_cases=test_cases,
            )
    elif model_document.type == ModelDocument.Type.REGISTRY:
        test_cases.extend(model_document.referencesDocument.keys())
    elif model_document.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
        test_cases.append(model_document)
    elif model_document.type == ModelDocument.Type.INSTANCE:
        test_id = get_document_id(model_document)
        expected_failure = isExpectedFailure(test_id, expected_failure_ids, required_locale_by_ids, system_locale)
        model_errors = sorted(cntlr.modelManager.modelXbrl.errors)
        expected_model_errors_list = sorted(expected_model_errors)
        param = pytest.param(
            {
                'status': 'pass' if model_errors == expected_model_errors_list else 'fail',
                'expected': expected_model_errors_list,
                'actual': model_errors,
            },
            id=test_id,
            marks=[pytest.mark.xfail()] if expected_failure else [],
        )
        results.append(param)
    else:
        raise Exception('Unhandled model document type: {}'.format(model_document.type))


def isExpectedFailure(
        test_id: str,
        expected_failure_ids: frozenset[str],
        required_locale_by_ids: dict[str, re.Pattern[str]],
        system_locale: str,
) -> bool:
    if test_id in expected_failure_ids:
        return True
    if test_id in required_locale_by_ids:
        return not required_locale_by_ids[test_id].search(system_locale)
    return False
