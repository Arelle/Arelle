from collections import Counter
import os.path
from pathlib import PurePosixPath

import pytest

from arelle.CntlrCmdLine import parseAndRun
from arelle import ModelDocument, PackageManager, PluginManager


def get_test_data(args, expected_failure_ids=frozenset(), expected_empty_testcases=frozenset()):
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :type args: list of strings
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :type expected_failure_ids: frozenset of strings
    :param expected_empty_testcases: The set of paths of empty testcases, relative to the suite zip
    :type expected_empty_testcases: frozenset of strings
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    :rtype: list of ::class:: `~pytest.param`
    """
    cntlr = parseAndRun(args)
    try:
        results = []
        test_cases_with_no_variations = set()
        model_document = cntlr.modelManager.modelXbrl.modelDocument
        if model_document is not None:
            test_cases = []
            if model_document.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
                test_cases.append(model_document)
            elif model_document.type == ModelDocument.Type.TESTCASESINDEX:
                test_cases = sorted(model_document.referencesDocument.keys(), key=lambda doc: doc.uri)
            else:
                raise Exception('Unhandled model document type: {}'.format(model_document.type))
            for test_case in test_cases:
                path = PurePosixPath(test_case.uri)
                test_case_path_tail = path.parts[-3:-1] if path.name == 'index.xml' else path.parts[-2:]
                if not getattr(test_case, "testcaseVariations", None) and os.path.relpath(test_case.filepath, model_document.modelXbrl.fileSource.basefile) not in expected_empty_testcases:
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
