import os
import pytest

from arelle.CntlrCmdLine import parseAndRun
from arelle import ModelDocument, PackageManager, PluginManager


def get_test_data(args, expected_failure_ids=frozenset()):
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :type args: list of strings
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :type expected_failure_ids: frozenset of strings
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
                uri_dir_parts = os.path.dirname(test_case.uri).split('/')
                test_case_dir = '/'.join(uri_dir_parts[-2:])
                if not getattr(test_case, "testcaseVariations", None):
                    test_cases_with_no_variations.add(test_case_dir)
                else:
                    for mv in test_case.testcaseVariations:
                        test_id = '{}/{}'.format(test_case_dir, str(mv.id or mv.name))
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
        nonexistent_expected_failure_ids = expected_failure_ids - {p.id for p in results}
        if nonexistent_expected_failure_ids:
            raise Exception(f"Some expected failure IDs don't match any test cases: {sorted(nonexistent_expected_failure_ids)}.")
        return results
    finally:
        cntlr.modelManager.close()
        PackageManager.close()
        PluginManager.close()
