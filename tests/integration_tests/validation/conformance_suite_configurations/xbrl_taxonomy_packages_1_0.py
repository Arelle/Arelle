from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('taxonomy-package-conformance.zip'),
            entry_point=Path('index.xml'),
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-taxonomy-packages-taxonomy-packages-1.0.html',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    test_case_result_options='match-any',
)
