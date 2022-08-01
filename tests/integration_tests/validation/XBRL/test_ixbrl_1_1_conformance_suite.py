import os.path
import pytest
from shutil import unpack_archive

from tests.integration_tests.validation.validation_util import get_test_data

# from https://specifications.xbrl.org/work-product-index-inline-xbrl-inline-xbrl-1.1.html
CONFORMANCE_SUITE_ZIP = 'tests/resources/conformance_suites/inlineXBRL-1.1-conformanceSuite-2020-04-08.zip'
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/inlineXBRL-1.1-conformanceSuite-2020-04-08'

ARGS = [
    '--file', os.path.join(CONFORMANCE_SUITE, 'index.xml'),
    '--keepOpen',
    '--packages', os.path.join(CONFORMANCE_SUITE, 'schemas/www.example.com.zip'),
    '--plugins', 'inlineXbrlDocumentSet.py|../examples/plugin/testcaseIxExpectedHtmlFixup.py',
    '--validate',
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

if not os.path.exists(CONFORMANCE_SUITE):
    unpack_archive(CONFORMANCE_SUITE_ZIP, extract_dir=os.path.dirname(CONFORMANCE_SUITE))
TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_ixbrl_1_1_conformance_suite(result):
    assert result['status'] == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
