from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

TIMING = {
    'audited_abridged_LLP_accounts/testcase.xml': 15.487,
    'audited_company_abridged_accounts/testcase.xml': 22.816,
    'audited_medium_LLP/testcase.xml': 13.015,
    'audited_medium_company/testcase.xml': 12.880,
    'audited_small_LLP/testcase.xml': 11.441,
    'audited_small_company/testcase.xml': 11.741,
    'jfcvc/3312-testcase.xml': 8.009,
    'jfcvc/3315-testcase.xml': 7.891,
    'unaudited_company_abbreviated_accounts/testcase.xml': 23.917,
    'unaudited_company_abridged_accounts/testcase.xml': 26.535,
    'unaudited_company_group_accounts/testcase.xml': 25.746,
    'unaudited_dormant_company/testcase.xml': 30.359,
    'unaudited_dormant_llp/testcase.xml': 22.251,
    'unaudited_llp_abbreviated_accounts/testcase.xml': 19.648,
    'unaudited_llp_abridged_accounts/testcase.xml': 23.202,
    'unaudited_llp_full_accounts/testcase.xml': 19.965,
    'unaudited_llp_group_accounts/testcase.xml': 22.312,
    'unaudited_micro_company/testcase.xml': 30.898,
    'unaudited_micro_llp/testcase.xml': 22.313,
    'unaudited_small_company_full_accounts/testcase.xml': 22.876,
}

config = ConformanceSuiteConfig(
    approximate_relative_timing=TIMING,
    args=[
        '--hmrc',
    ],
    file='index.xml',
    info_url='https://www.gov.uk/government/organisations/hm-revenue-customs',
    local_filepath='HMRC',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/HMRC'}),
    shards=4,
)
