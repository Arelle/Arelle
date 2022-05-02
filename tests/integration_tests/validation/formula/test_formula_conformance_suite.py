import os
import pytest

from tests.integration_tests.validation.validation_util import get_test_data

# from https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html
TEST_SUITE = 'tests/resources/conformance_suites/formula.zip/formula/tests'
ARGS = [
    '--file', os.path.abspath(os.path.join(TEST_SUITE, 'index.xml')),
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--validate',
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_formula(result):
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
