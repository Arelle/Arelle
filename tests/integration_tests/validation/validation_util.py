import os
import pytest

from arelle.CntlrCmdLine import parseAndRun
from arelle import ModelDocument, PackageManager, PluginManager


def get_test_data(args):
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param args: The args to be parsed by arelle in order to correctly produce the desired result set
    :type args: list of strings
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    :rtype: list of ::class:: `~pytest.param`
    """
    cntlr = parseAndRun(args)
    try:
        results = []
        model_document = cntlr.modelManager.modelXbrl.modelDocument
        if model_document is not None:
            test_cases = []
            if model_document.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
                test_cases.append(model_document)
            elif model_document.type == ModelDocument.Type.TESTCASESINDEX:
                test_cases = sorted(model_document.referencesDocument.keys(), key=lambda doc: doc.uri)
            else:
                raise 'Unhandled model document type: {}'.format(model_document.type)
            for test_case in test_cases:
                uri_dir_parts = os.path.dirname(test_case.uri).split('/')
                test_case_dir = '/'.join(uri_dir_parts[-2:])
                if hasattr(test_case, "testcaseVariations"):
                    for mv in test_case.testcaseVariations:
                        param = pytest.param(
                            {
                                'status': mv.status,
                                'expected': mv.expected,
                                'actual': mv.actual
                            },
                            id='{}/{}'.format(test_case_dir, str(mv.id or mv.name))
                        )
                        results.append(param)
        return results
    finally:
        cntlr.modelManager.close()
        PackageManager.close()
        PluginManager.close()
