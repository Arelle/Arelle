from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--formula', 'run',
        '--calcPrecision',
    ],
    expected_failure_ids=frozenset([
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
    ]),
    file='XBRL-CONF-2014-12-10/xbrl.xml',
    info_url='https://specifications.xbrl.org/work-product-index-group-base-spec-base-spec.html',
    local_filepath='XBRL-CONF-2014-12-10.zip',
    name=PurePath(__file__).stem,
    public_download_url='https://www.xbrl.org/2014/XBRL-CONF-2014-12-10.zip',
)
