import os
import zipfile

import pytest

from arelle.CntlrCmdLine import parseAndRun
from tests.integration_tests.validation.validation_util import get_test_data

# from https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html
REGISTRY_CONFORMANCE_SUITE = 'tests/resources/conformance_suites/utr/registry/utr-conf-cr-2013-05-17.zip/utr-conf-cr-2013-05-17/2013-05-17'
STRUCTURE_CONFORMANCE_SUITE_ZIP = 'tests/resources/conformance_suites/utr/structure/utr-structure-conf-cr-2013-11-18.zip'
STRUCTURE_CONFORMANCE_SUITE = os.path.join(STRUCTURE_CONFORMANCE_SUITE_ZIP, 'conf/utr-structure')
ARGS = [
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--utr',
    '--validate',
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity','offline'])

REGISTRY_ARGS = ARGS + [
    '--file', os.path.join(REGISTRY_CONFORMANCE_SUITE, 'index.xml'),
    '--utrUrl', 'tests/resources/conformance_suites/utr/registry/utr.xml',
]
STRUCTURE_ARGS = ARGS + [
    '--file', os.path.join(STRUCTURE_CONFORMANCE_SUITE, 'index.xml'),
    '--utrUrl', os.path.join(STRUCTURE_CONFORMANCE_SUITE, 'utr-for-structure-conformance-tests.xml'),
]

REGISTRY_TEST_DATA = get_test_data(REGISTRY_ARGS)
STRUCTURE_TEST_DATA = get_test_data(STRUCTURE_ARGS)


def gen_malformed_utr_paths():
    with zipfile.ZipFile(STRUCTURE_CONFORMANCE_SUITE_ZIP, 'r') as zipf:
        for f in zipfile.Path(zipf, 'conf/utr-structure/malformed-utrs/').iterdir():
            if f.is_file() and f.name.endswith('.xml'):
                yield f.at


@pytest.mark.parametrize("result", REGISTRY_TEST_DATA)
def test_utr_registry_conformance_suite(result):
    assert result['status'] == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )


@pytest.mark.parametrize("result", STRUCTURE_TEST_DATA)
def test_utr_structure_conformance_suite(result):
    assert result['status'] == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )


@pytest.mark.parametrize('malformed_utr_file', gen_malformed_utr_paths())
def test_utr_structure_malformed_utrs_conformance_suite(malformed_utr_file):
    args = ARGS + [
        # any valid file that refers to units, hopefully small, since it's not the point of the test
        '--file', os.path.join(STRUCTURE_CONFORMANCE_SUITE, 'tests', '01-simple', 'simpleValid.xml'),
        '--utrUrl', os.path.join(STRUCTURE_CONFORMANCE_SUITE_ZIP, malformed_utr_file),
    ]
    controller = parseAndRun(args)
    errors = controller.modelManager.modelXbrl.errors
    # when it can't find the file, it returns 'arelleUtrLoader:error'
    assert errors and errors != ['arelleUtrLoader:error']
