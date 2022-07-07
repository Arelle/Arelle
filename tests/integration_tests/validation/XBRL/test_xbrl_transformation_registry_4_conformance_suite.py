import os
import pytest
from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/trr-4.0.zip'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'testcase.xml')),
    '--formula', 'run',
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_xbrl_transformation_registry_4_conformance_suite(result):
    """
    Test the XBRL Transformation Registry 4 Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
