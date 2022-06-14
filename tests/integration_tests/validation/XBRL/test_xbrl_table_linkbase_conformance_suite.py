import os
import pytest
from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/table-linkbase-conf-2014-03-18.zip/conf'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'testcases-index.xml')),
    '--formula', 'run',
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

TEST_DATA = get_test_data(ARGS)

EXPECTED_FAILURE_IDS = []


@pytest.mark.parametrize("result", TEST_DATA)
def test_xbrl_table_linkbase_conformance_suite(result, request):
    """
    Test the XBRL Table Linkbase Conformance Suite
    """
    if request.node.callspec.id in EXPECTED_FAILURE_IDS:
        pytest.xfail(f"Test '{request.node.callspec.id}' not supported yet")
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
