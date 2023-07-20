from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'efm-pragmatic',
        '--formula', 'run',
        '--plugins', 'validate/EFM|inlineXbrlDocumentSet|EdgarRenderer',
    ],
    expected_empty_testcases=frozenset([
        'conf/605-instance-syntax/605-45-cover-page-facts-general-case/605-45-cover-page-facts-general-case-testcase.xml',
        'conf/609-linkbase-syntax/609-10-general-namespace-specific-custom-arc-restrictions/609-10-general-namespace-specific-custom-arc-restrictions-testcase.xml',
        'conf/624-rendering/09-start-end-labels/gd/09-start-end-labels-gd-testcase.xml',
        'conf/624-rendering/14-cash-flows/gd/14-cash-flows-gd-testcase.xml',
        'conf/624-rendering/15-equity-changes/gw/15-equity-changes-gw-testcase.xml',
        'conf/624-rendering/18-numeric/gd/18-numeric-gd-testcase.xml',
        'conf/626-rendering-syntax/626-03-no-matching-durations/626-03-no-matching-durations-testcase.xml',
    ]),
    file='conf/testcases.xml',
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    local_filepath='efm-66-230620.zip',
    name=PurePath(__file__).stem,
    public_download_url='https://www.sec.gov/files/edgar/efm-66-230620.zip',
)
