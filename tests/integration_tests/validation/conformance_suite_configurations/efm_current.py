from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'efm-pragmatic-preview',
        '--formula', 'run',
        '--plugins', 'validate/EFM|inlineXbrlDocumentSet|EdgarRenderer',
    ],
    expected_empty_testcases=frozenset([
        'conf/605-instance-syntax/605-45-cover-page-facts-general-case/605-45-cover-page-facts-general-case-testcase.xml',
        'conf/609-linkbase-syntax/609-10-general-namespace-specific-custom-arc-restrictions/609-10-general-namespace-specific-custom-arc-restrictions-testcase.xml',
        'conf/624-rendering/09-start-end-labels/gd/09-start-end-labels-gd-testcase.xml',
        'conf/624-rendering/14-cash-flows/gd/14-cash-flows-gd-testcase.xml',
        'conf/624-rendering/18-numeric/gd/18-numeric-gd-testcase.xml',
        'conf/624-rendering/15-equity-changes/gw/15-equity-changes-gw-testcase.xml',
    ]),
    file='conf/testcases.xml',
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    local_filepath='efm_conformance_suite_2022.zip',
    name=PurePath(__file__).stem,
    public_download_url='https://www.sec.gov/info/edgar/ednews/efmtest/efm-64d-221128.zip'
)
