from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--plugin', 'loadFromOIM',
        '--plugin', '../../arelle/examples/plugin/testcaseCalc11ValidateSetup.py',
    ],
    expected_failure_ids=frozenset([
        # The loadFromOIM plugin is required to load the conformance suite json
        # files. However, OIM validation raises xbrlxe:unsupportedTuple for
        # tuples which then raises calc11e:tuplesInReportWarning in calc 1.1.
        # This isn't modeled in the conformance suite, but expected if both
        # calc 1.1 and OIM validation are performed together.
        # https://www.xbrl.org/Specification/xbrl-xml/REC-2021-10-13/xbrl-xml-REC-2021-10-13.html#unsupportedTuple
        # https://www.xbrl.org/Specification/calculation-1.1/REC-2023-02-22/calculation-1.1-REC-2023-02-22.html#error-calc11e-tuplesinreportwarning
        'calculation-1.1-conformance-2023-02-22/calc11/oim-tuple-consistent-round',
        'calculation-1.1-conformance-2023-02-22/calc11/oim-tuple-consistent-truncate',
        'calculation-1.1-conformance-2023-02-22/calc11/oim-tuple-ignored-calculation-round',
        'calculation-1.1-conformance-2023-02-22/calc11/oim-tuple-ignored-calculation-truncate',
        'calculation-1.1-conformance-2023-02-22/xbrl21/oim-tuple-consistent-round',
        'calculation-1.1-conformance-2023-02-22/xbrl21/oim-tuple-consistent-truncate',
        'calculation-1.1-conformance-2023-02-22/xbrl21/oim-tuple-ignored-calculation-round',
        'calculation-1.1-conformance-2023-02-22/xbrl21/oim-tuple-ignored-calculation-truncate',

        # Similar to the above, validation errors other than
        # xbrlxe:unsupportedTuple are expected to raise
        # calc11e:oimIncompatibleReportWarning during calc 1.1 validation.
        # https://www.xbrl.org/Specification/calculation-1.1/REC-2023-02-22/calculation-1.1-REC-2023-02-22.html#error-calc11e-oimincompatiblereportwarning
        'calculation-1.1-conformance-2023-02-22/calc11/oim-illegal-fraction-item-round',
        'calculation-1.1-conformance-2023-02-22/calc11/oim-illegal-fraction-item-truncate',
        'calculation-1.1-conformance-2023-02-22/xbrl21/oim-illegal-fraction-item-round',
        'calculation-1.1-conformance-2023-02-22/xbrl21/oim-illegal-fraction-item-truncate',
    ]),
    file='calculation-1.1-conformance-2023-02-22/index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-calculations-2-calculations-1-1.html',
    local_filepath='calculation-1.1-conformance-2023-02-22.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
)
