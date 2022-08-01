import os
import pytest

from tests.integration_tests.validation.validation_util import get_test_data

# part of https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/60111 AssertionSeverity-2.0-Processing.zip/60111 AssertionSeverity-2.0-Processing'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, '60111 Assertion Severity 2.0 Processing.xml')),
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--validate',
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_assertion_severity_2_0(result):
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
