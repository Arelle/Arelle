import os
import pytest
from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/XBRL-CONF-2014-12-10.zip'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'xbrl.xml')),
    '--formula', 'run',
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--calcPrecision',
    '--validate'
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

EXPECTED_FAILURE_IDS = frozenset([
    # 202.02b in the absence of source/target constraints, an empty href doesn't pose a problem
    # 202-02b-HrefResolutionCounterExample-custom.xml Expected: valid, Actual: arelle:hrefWarning
    '200-linkbase/202-xlinkLocator.xml/V-02b',
    # Tests that a decimals 0 value 0 is not treated as precision 0 (invalid) but as numeric zero.
    # In the prior approach where decimals 0 value 0 converted to precision 0 value 0, this would have been invalid.
    # 320-30-BindCalculationInferDecimals-instance.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
    '300-instance/320-CalculationBinding.xml/V-30',
    # Edge case tests that decimal rounding with is performed.
    # 320-31-BindCalculationInferDecimals-instance.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
    '300-instance/320-CalculationBinding.xml/V-31',
    # Checks that .5 rounds half to nearest even sum.
    # 320-32-BindCalculationInferDecimals-instance.xbrl Expected: invalid, Actual: valid
    '300-instance/320-CalculationBinding.xml/V-32',
    # Checks that .5 rounds half to nearest even regardless whether a processor uses float sum.
    # 320-34-BindCalculationInferDecimals-instance.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
    '300-instance/320-CalculationBinding.xml/V-34',
    # 397-28-PrecisionDifferentScales.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
    '300-instance/397-Testcase-SummationItem.xml/V-28',
])

TEST_DATA = get_test_data(ARGS, expected_failure_ids=EXPECTED_FAILURE_IDS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_xbrl_conformance_suite(result):
    """
    Test the XBRL 2.1 Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
