import os
import pytest
from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/oim-conf-2021-10-13.zip'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'oim-index.xml')),
    '--formula', 'run',
    '--httpsRedirectCache',
    '--keepOpen',
    '--plugins', 'loadFromOIM',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_xbrl_oim_conformance_suite(result):
    """
    Test the XBRL Open Information Model 1.0 Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
