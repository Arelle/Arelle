import os
import pytest


from tests.integration_tests.validation.validation_util import get_test_data

# from https://www.sec.gov/structureddata/osdinteractivedatatestsuite
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/efm_conformance_suite_2022.zip/conf'
EFM_PLUGIN = 'validate/EFM'
IXDS_PLUGIN = 'inlineXbrlDocumentSet'
EDGARRENDERER_PLUGIN = 'EdgarRenderer'
PLUGINS = [EFM_PLUGIN, IXDS_PLUGIN, EDGARRENDERER_PLUGIN]
ARGS = [
    '--disclosureSystem', 'efm-pragmatic',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'testcases.xml')),
    '--formula', 'run',
    '--keepOpen',
    '--plugins', '|'.join(PLUGINS),
    '--testcaseResultsCaptureWarnings',
    '--validate'
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity','offline'])

EXPECTED_EMPTY_TESTCASES = frozenset([
    'conf/605-instance-syntax/605-45-cover-page-facts-general-case/605-45-cover-page-facts-general-case-testcase.xml',
    'conf/609-linkbase-syntax/609-10-general-namespace-specific-custom-arc-restrictions/609-10-general-namespace-specific-custom-arc-restrictions-testcase.xml',
    'conf/624-rendering/09-start-end-labels/gd/09-start-end-labels-gd-testcase.xml',
    'conf/624-rendering/14-cash-flows/gd/14-cash-flows-gd-testcase.xml',
    'conf/624-rendering/18-numeric/gd/18-numeric-gd-testcase.xml',
    'conf/624-rendering/15-equity-changes/gw/15-equity-changes-gw-testcase.xml',
])
TEST_DATA = get_test_data(ARGS, expected_empty_testcases=EXPECTED_EMPTY_TESTCASES)


@pytest.mark.parametrize("result", TEST_DATA)
def test_efm_ixbrl_conformance_suite(result):
    """
    Test the EFM Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
