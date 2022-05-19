import os
import pytest


from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/esef_conformance_suite_2021.zip/esef_conformance_suite_2021/esef_conformance_suite_2021'
PLUGIN = 'validate/ESEF'
ARGS = [
    '--disclosureSystem', 'esef',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'index_inline_xbrl.xml')),
    '--formula', 'run',
    '--keepOpen',
    '--plugins', PLUGIN,
    '--testcaseResultsCaptureWarnings',
    '--validate'
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity','offline'])

TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_esef_ixbrl_conformance_suite(result):
    """
    Test the ESEF IXBRL Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
