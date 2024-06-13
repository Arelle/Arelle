from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        "--validateXmlOim",
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('calculation-1.1-conformance-2023-12-20.zip'),
            entry_point=Path('calculation-1.1-conformance-2023-12-20/index.xml'),
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-calculations-2-calculations-1-1.html',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'../../tests/plugin/testcaseCalc11ValidateSetup.py'}),
    test_case_result_options='match-any',
)
